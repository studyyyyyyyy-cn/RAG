"""Convert knowledge graph nodes and edges into natural language text for vector embedding.

Format:
  Node:  "IBM是一家总部位于美国的云服务公司"
  Edge:  "IBM公司正在研发量子计算"

Each node/edge is embedded and stored in a dedicated Milvus collection (kb_{kb_id}_graph).
Idempotent: re-running only embeds new nodes/edges not already in the vector store.
"""

import json
import logging

from app.core.graph_store import graph_store, GraphEntity, GraphRelation
from app.core.embedder import get_embedder
from app.core.vector_store import vector_store
from app.config import settings

logger = logging.getLogger(__name__)

# Collection name suffix for graph vectors
GRAPH_COLLECTION_SUFFIX = "_graph"


def _graph_collection_name(kb_id: str) -> str:
    """Milvus collection name for graph vectors."""
    return f"kb_{kb_id.replace('-', '_')}{GRAPH_COLLECTION_SUFFIX}"


# ── Natural language conversion ──────────────────────────────────────────

def node_to_text(entity: dict) -> str:
    """Convert a Neo4j entity node to natural language description.

    Example:
      entity = {name: "IBM", entity_type: "公司",
                properties: {总部: "美国", 业务: "云服务"}}
      → "IBM是一家公司，总部位于美国，业务为云服务。"
    """
    name = entity.get("name", "")
    etype = entity.get("entity_type", "")

    parts = [name]

    # Entity type as category
    type_labels = {
        "PERSON": "人物", "ORGANIZATION": "组织", "PRODUCT": "产品",
        "CONCEPT": "概念", "LOCATION": "地点", "TIME": "时间",
        "EVENT": "事件", "ATTRIBUTE": "属性",
    }
    label = type_labels.get(etype, etype)
    if label:
        parts.append(f"是一个{label}")

    # Properties (exclude internal fields)
    props = entity.get("properties", {}) or {}
    skip_keys = {"kb_id", "id", "name", "entity_type", "aliases"}
    prop_strs = []
    for k, v in props.items():
        if k in skip_keys:
            continue
        prop_strs.append(f"{k}为{v}")
    if prop_strs:
        parts.append("，" + "，".join(prop_strs))

    return "".join(parts) + "。"


def edge_to_text(source_name: str, target_name: str, relation: str) -> str:
    """Convert a relation edge to natural language description.

    Example:
      edge = {source: "IBM", target: "量子计算", relation: "研发"}
      → "IBM正在研发量子计算。"
    """
    return f"{source_name}{relation}{target_name}。"


# ── Embedding pipeline ────────────────────────────────────────────────────

async def embed_graph_to_vector(
    kb_id: str,
    nodes: list[dict],
    edges: list[dict],
    embedding_model: str | None = None,
    force: bool = False,
) -> dict:
    """Embed graph nodes and edges into the vector store.

    Skips already-embedded entities (tracked by entity_id / edge_key in Milvus).

    Args:
        kb_id: Knowledge base ID.
        nodes: List of Neo4j node dicts with id, name, entity_type, properties.
        edges: List of Neo4j edge dicts with source, target, relation.
        embedding_model: Embedding model name.
        force: If True, re-embed everything (drops existing graph collection).

    Returns:
        dict with counts of newly embedded nodes/edges.
    """
    model_name = embedding_model or settings.DEFAULT_EMBEDDING_MODEL
    collection_name = _graph_collection_name(kb_id)

    # Get embedder
    embedder = get_embedder(model_name, settings.EMBEDDING_DEVICE)
    dim = embedder.dim

    # Create or verify collection
    vector_store.create_collection(f"{kb_id}{GRAPH_COLLECTION_SUFFIX}", dense_dim=dim)

    # Force re-embed everything
    if force:
        vector_store.delete_by_doc(f"{kb_id}{GRAPH_COLLECTION_SUFFIX}", "__all__")
        logger.info(f"Force-cleared graph vectors for KB {kb_id}")

    # Get already-embedded IDs from Milvus
    existing_ids = _get_existing_graph_ids(kb_id)
    logger.info(f"KB {kb_id}: {len(existing_ids)} existing graph vectors, "
                f"{len(nodes)} nodes, {len(edges)} edges")

    # ── Build texts for new nodes ──
    node_texts = []
    node_ids = []      # Milvus row IDs
    node_entity_ids = []  # Neo4j entity IDs for dedup

    for node in nodes:
        entity_id = node.get("id", "")
        if entity_id in existing_ids:
            continue
        text = node_to_text(node)
        node_texts.append(text)
        node_entity_ids.append(entity_id)

    # ── Build texts for new edges ──
    edge_texts = []
    edge_ids = []
    edge_keys = []  # "source|target|relation" for dedup

    # Build a node name lookup for edge text conversion
    node_names = {n.get("id", ""): n.get("name", "") for n in nodes}

    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        rel = edge.get("relation", "")
        edge_key = f"{src}|{tgt}|{rel}"
        if edge_key in existing_ids:
            continue
        src_name = node_names.get(src, src)
        tgt_name = node_names.get(tgt, tgt)
        text = edge_to_text(src_name, tgt_name, rel)
        edge_texts.append(text)
        edge_keys.append(edge_key)

    # ── Embed and insert ──
    all_texts = node_texts + edge_texts
    if not all_texts:
        logger.info(f"KB {kb_id}: All graph entities already embedded, nothing to do")
        return {"nodes_embedded": 0, "edges_embedded": 0, "skipped": len(nodes) + len(edges)}

    embeddings = embedder.embed_documents(all_texts)
    dense_vecs = embeddings["dense"]
    sparse_vecs = embeddings.get("sparse")

    # Insert nodes
    if node_texts:
        n_data = []
        for i, text in enumerate(node_texts):
            n_data.append({
                "id": f"node_{node_entity_ids[i]}",
                "chunk_id": f"graph_node_{node_entity_ids[i]}",
                "doc_id": f"graph_{kb_id}",
                "dense_vector": dense_vecs[i].tolist() if hasattr(dense_vecs[i], 'tolist') else dense_vecs[i],
                "sparse_vector": "" if sparse_vecs is None else json.dumps(sparse_vecs[i], default=str),
                "content": text[:8000],
            })
        vector_store.client.insert(_graph_collection_name(kb_id), n_data)
        logger.info(f"Embedded {len(node_texts)} graph nodes for KB {kb_id}")

    # Insert edges
    if edge_texts:
        offset = len(node_texts)
        e_data = []
        for i, text in enumerate(edge_texts):
            idx = offset + i
            e_data.append({
                "id": f"edge_{edge_keys[i].replace('|', '_')[:100]}",
                "chunk_id": f"graph_edge_{edge_keys[i].replace('|', '_')[:100]}",
                "doc_id": f"graph_{kb_id}",
                "dense_vector": dense_vecs[idx].tolist() if hasattr(dense_vecs[idx], 'tolist') else dense_vecs[idx],
                "sparse_vector": "" if sparse_vecs is None else json.dumps(sparse_vecs[idx], default=str),
                "content": text[:8000],
            })
        vector_store.client.insert(_graph_collection_name(kb_id), e_data)
        logger.info(f"Embedded {len(edge_texts)} graph edges for KB {kb_id}")

    return {
        "nodes_embedded": len(node_texts),
        "edges_embedded": len(edge_texts),
        "skipped": len(nodes) + len(edges) - len(node_texts) - len(edge_texts),
    }


def _get_existing_graph_ids(kb_id: str) -> set[str]:
    """Get set of already-embedded graph entity/edge IDs from Milvus.

    Reads all doc_ids from the graph collection to determine what's been embedded.
    Uses a simple approach: scan existing vectors and collect unique entity references.
    """
    # Since Milvus Lite doesn't support complex queries well,
    # we check by scanning the collection metadata via the in-memory path
    collection_name = _graph_collection_name(kb_id)

    # Try Milvus describe
    try:
        if not vector_store._use_memory and vector_store.client:
            if vector_store.client.has_collection(collection_name):
                # Query all IDs from the collection
                results = vector_store.client.query(
                    collection_name=collection_name,
                    filter="",
                    output_fields=["chunk_id"],
                    limit=10000,
                )
                ids = set()
                for r in results:
                    chunk_id = r.get("chunk_id", "")
                    if chunk_id.startswith("graph_node_"):
                        ids.add(chunk_id[len("graph_node_"):])
                    elif chunk_id.startswith("graph_edge_"):
                        # Convert back to edge key format
                        edge_part = chunk_id[len("graph_edge_"):]
                        ids.add(edge_part.replace("_", "|"))
                return ids
    except Exception as e:
        logger.debug(f"Could not query graph collection (may not exist yet): {e}")

    # Fallback: check in-memory
    try:
        mem = vector_store.client
        if hasattr(mem, 'collections') and collection_name in mem.collections:
            ids = set()
            for meta in mem.collections[collection_name].get("metadata", []):
                chunk_id = meta.get("chunk_id", "")
                if chunk_id.startswith("graph_node_"):
                    ids.add(chunk_id[len("graph_node_"):])
                elif chunk_id.startswith("graph_edge_"):
                    ids.add(chunk_id[len("graph_edge_"):].replace("_", "|"))
            return ids
    except Exception:
        pass

    return set()
