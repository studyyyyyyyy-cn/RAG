"""Hybrid retriever: combines vector search with reranking and parent-chunk context."""
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


@dataclass
class RetrievalResponse:
    """Complete retrieval response."""
    results: list[RetrievalResult]
    confidence: float
    confidence_label: str


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
    search_results = vector_store.hybrid_search(
        kb_id=kb_id,
        dense_query=dense_query,
        sparse_query=sparse_query,
        top_k=top_k,
    )

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

    # 5. Confidence
    confidence = compute_confidence(rerank_scores, settings.CONFIDENCE_THRESHOLD)
    from app.core.confidence import confidence_label
    label = confidence_label(confidence)

    return RetrievalResponse(results=results, confidence=confidence, confidence_label=label)
