"""Hybrid retriever: combines vector search with reranking, parent-chunk context, and graph retrieval."""
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedder import get_embedder
from app.core.vector_store import vector_store
from app.core.reranker import get_reranker
from app.core.confidence import compute_confidence
from app.models.chunk import Chunk
from app.models.document import Document
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Final retrieval result with chunk text and metadata."""
    chunk_id: str
    content: str
    score: float
    page_number: int | None = None
    section_title: str | None = None
    doc_id: str | None = None
    parent_content: str | None = None
    metadata: dict = field(default_factory=dict)
    graph_context: str | None = None  # Knowledge graph context for this result


@dataclass
class RetrievalResponse:
    """Complete retrieval response."""
    results: list[RetrievalResult]
    confidence: float
    confidence_label: str
    graph_context: str | None = None  # Aggregated graph context for the query


async def retrieve(
    query: str,
    kb_id: str,
    db: AsyncSession,
    embedding_model: str | None = None,
    top_k: int | None = None,
    top_n: int | None = None,
) -> RetrievalResponse:
    """Full retrieval pipeline: embed → hybrid search → rerank → parent context.

    Steps:
    1. Embed query (dense + sparse)
    2. Milvus hybrid search (dense + sparse with RRF)
    3. Cross-Encoder rerank top-K → top-N
    4. Fetch parent chunk context from DB
    5. Compute confidence score
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    top_n = top_n or settings.RERANK_TOP_N

    # 1. Embed the query
    embedding_model = embedding_model or settings.DEFAULT_EMBEDDING_MODEL
    embedder = get_embedder(embedding_model, settings.EMBEDDING_DEVICE)
    query_embedding = embedder.embed_query(query)

    dense_query = query_embedding["dense"]
    sparse_query = query_embedding.get("sparse")

    # 2. Hybrid search in Milvus
    logger.info(f"Searching KB {kb_id} with query embedding dim={dense_query.shape if hasattr(dense_query, 'shape') else '?'}")
    try:
        search_results = vector_store.hybrid_search(
            kb_id=kb_id,
            dense_query=dense_query,
            sparse_query=sparse_query,
            top_k=top_k,
        )
        logger.info(f"Retrieved {len(search_results)} results from vector search")
    except Exception as e:
        logger.warning(f"Vector search failed (may need to re-chunk docs): {e}")
        search_results = []

    if not search_results:
        return RetrievalResponse(results=[], confidence=0.0, confidence_label="very_low")

    # 3. Rerank with Cross-Encoder
    passages = [r.content for r in search_results]
    reranker = get_reranker(settings.DEFAULT_RERANKER_MODEL, settings.EMBEDDING_DEVICE)
    reranked = reranker.rerank(query, passages, top_n=top_n)

    # 4. Fetch chunk metadata and parent content from DB (batch queries)
    results: list[RetrievalResult] = []
    rerank_scores = []

    # Collect all chunk IDs and batch-fetch
    chunk_ids = [search_results[idx].chunk_id for idx, _ in reranked if search_results[idx].chunk_id]
    parent_ids = set()

    chunks_map: dict[str, Chunk] = {}
    if chunk_ids:
        chunk_result = await db.execute(select(Chunk).where(Chunk.id.in_(chunk_ids)))
        for c in chunk_result.scalars():
            chunks_map[c.id] = c
            if c.parent_chunk_id:
                parent_ids.add(c.parent_chunk_id)

    # Batch-fetch parent chunks
    parents_map: dict[str, Chunk] = {}
    if parent_ids:
        parent_result = await db.execute(select(Chunk).where(Chunk.id.in_(list(parent_ids))))
        for p in parent_result.scalars():
            parents_map[p.id] = p

    # Batch-fetch documents
    doc_ids = list({c.doc_id for c in chunks_map.values() if c.doc_id})
    docs_map: dict[str, Document] = {}
    if doc_ids:
        doc_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        for d in doc_result.scalars():
            docs_map[d.id] = d

    for original_idx, score in reranked:
        sr = search_results[original_idx]
        rerank_scores.append(score)

        chunk = chunks_map.get(sr.chunk_id) if sr.chunk_id else None

        parent_content = None
        if chunk and chunk.parent_chunk_id:
            parent_chunk = parents_map.get(chunk.parent_chunk_id)
            if parent_chunk:
                parent_content = parent_chunk.content

        # Get document name
        doc_name = "未知文档"
        if chunk and chunk.doc_id:
            doc = docs_map.get(chunk.doc_id)
            if doc:
                doc_name = doc.filename

        results.append(RetrievalResult(
            chunk_id=sr.chunk_id,
            content=sr.content or (chunk.content if chunk else ""),
            score=score,
            page_number=chunk.page_number if chunk else None,
            section_title=chunk.section_title if chunk else None,
            doc_id=str(chunk.doc_id) if chunk else None,
            parent_content=parent_content,
            metadata={"source": doc_name},
        ))

    # 5. Graph context: find best-matching entity from fused results, get Neo4j neighborhood
    graph_context = None
    try:
        graph_context = await _retrieve_graph_context(query, kb_id, dense_query)
    except Exception:
        pass  # Graph context is optional

    # 6. Confidence
    confidence = compute_confidence(rerank_scores, settings.CONFIDENCE_THRESHOLD)
    from app.core.confidence import confidence_label
    label = confidence_label(confidence)

    return RetrievalResponse(
        results=results,
        confidence=confidence,
        confidence_label=label,
        graph_context=graph_context,
    )


async def _retrieve_graph_context(
    query: str, kb_id: str, query_dense_vector
) -> str | None:
    """Search graph vector collection independently → find best matching entity → Neo4j neighborhood.

    Document chunks and graph entities are searched separately.
    Both are independently fed to the LLM as context.
    """
    from app.core.graph_store import graph_store as gs

    if not gs.ready:
        return None

    # Search graph vector collection
    try:
        graph_results = vector_store.search_graph(kb_id, query_dense_vector, top_k=5)
    except Exception:
        return None

    if not graph_results:
        return None

    # Find best matching entity from graph search results
    best_entity_id = None
    for gr in graph_results:
        cid = getattr(gr, 'chunk_id', '') or ''
        if cid.startswith('graph_node_'):
            best_entity_id = cid.replace('graph_node_', '')
            break
        elif cid.startswith('graph_edge_'):
            edge_key = cid.replace('graph_edge_', '').replace('_', '|')
            parts = edge_key.split('|')
            if len(parts) >= 1:
                best_entity_id = parts[0]
                break

    if not best_entity_id:
        return None

    # Get entity + neighborhood from Neo4j
    entity = gs.get_entity(best_entity_id)
    if not entity:
        return None

    subgraph = gs.get_neighbors(best_entity_id, hops=1)

    # Build natural language context with entity details + neighbors + relations
    parts = []

    entity_name = entity.get("name", "")
    entity_type = entity.get("entity_type", "")

    # Entity type labels
    type_labels = {"PERSON":"人物","ORGANIZATION":"组织","PRODUCT":"产品","CONCEPT":"概念",
                   "LOCATION":"地点","TIME":"时间","EVENT":"事件","ATTRIBUTE":"属性"}

    # Describe the matched entity with properties
    entity_label = type_labels.get(entity_type, entity_type)
    props = entity.get("properties", {}) or {}
    skip = {"kb_id", "id", "name", "entity_type", "aliases"}
    prop_desc = "，".join(f"{k}: {v}" for k, v in props.items() if k not in skip and v)
    if prop_desc:
        parts.append(f"核心实体: {entity_name}（{entity_label}，{prop_desc}）")
    else:
        parts.append(f"核心实体: {entity_name}（{entity_label}）")

    # Build name lookup for neighbors
    node_map = {n.get("id"): n for n in subgraph.nodes}

    # Describe relations with neighbor context
    if subgraph.edges:
        parts.append("关联关系：")
        seen = set()
        for e in subgraph.edges:
            src, tgt, rel = e.get("source",""), e.get("target",""), e.get("relation","")
            if src == best_entity_id:
                neighbor = node_map.get(tgt, {})
                n_name = neighbor.get("name", tgt)
                n_type = type_labels.get(neighbor.get("entity_type",""), neighbor.get("entity_type",""))
                n_props = neighbor.get("properties", {}) or {}
                n_desc = "，".join(f"{k}:{v}" for k,v in n_props.items() if k not in skip and v)
                desc = f"  {entity_name} {rel} {n_name}"
                if n_type: desc += f"（{n_type}）"
                if n_desc: desc += f" [{n_desc}]"
                if desc not in seen:
                    seen.add(desc)
                    parts.append(desc)
            elif tgt == best_entity_id:
                neighbor = node_map.get(src, {})
                n_name = neighbor.get("name", src)
                n_type = type_labels.get(neighbor.get("entity_type",""), neighbor.get("entity_type",""))
                n_props = neighbor.get("properties", {}) or {}
                n_desc = "，".join(f"{k}:{v}" for k,v in n_props.items() if k not in skip and v)
                desc = f"  {n_name} {rel} {entity_name}"
                if n_type: desc += f"（{n_type}）"
                if n_desc: desc += f" [{n_desc}]"
                if desc not in seen:
                    seen.add(desc)
                    parts.append(desc)

    return "\n".join(parts)
