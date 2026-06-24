"""Vector Store Status API — shows vector counts per KB, with reload+progress."""

import json
import sqlite3
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.llm_config import LLMConfig
from app.core.vector_store import vector_store
from app.core.graph_store import graph_store
from app.core.graph_to_vector import _graph_collection_name, embed_graph_to_vector
from app.core.embedder import get_embedder
from app.core.llm_manager import get_llm_config
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/vector-status")
async def get_vector_status():
    """Get vector store status for all knowledge bases."""
    db_path = Path(__file__).parent.parent.parent.parent / "data" / "ragapp.db"
    kbs = []
    try:
        conn = sqlite3.connect(str(db_path))
        kbs = list(conn.execute("SELECT id, name, doc_count FROM knowledge_bases"))
        conn.close()
    except Exception:
        pass

    results = []
    for kb_id, kb_name, doc_count in kbs:
        col_name = f"kb_{kb_id.replace('-', '_')}"
        graph_col = _graph_collection_name(kb_id)

        results.append({
            "kb_id": kb_id,
            "kb_name": kb_name,
            "doc_count": doc_count or 0,
            "chunk_vectors": _count_vectors(col_name),
            "graph_vectors": _count_vectors(graph_col),
            "neo4j_entities": graph_store.get_entity_count(kb_id) if graph_store.ready else 0,
            "neo4j_relations": _neo4j_rel_count(kb_id) if graph_store.ready else 0,
            "mode": "Milvus" if not vector_store._use_memory else "Memory",
        })

    return {
        "mode": "Milvus" if not vector_store._use_memory else "Memory",
        "knowledge_bases": results,
    }


@router.get("/kb/{kb_id}/reload-vectors")
async def reload_vectors_sse(kb_id: str):
    """SSE endpoint: re-embed all chunks and graph entities for a KB with live progress."""
    return StreamingResponse(
        _reload_stream(kb_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _reload_stream(kb_id: str):
    """Stream progress events while re-embedding everything."""
    try:
        yield _sse("start", {"kb_id": kb_id, "message": "开始重载向量..."})

        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if not kb:
                yield _sse("error", {"message": "知识库不存在"})
                return

            # Get LLM config (for graph extraction)
            llm_config = None
            try:
                r = await db.execute(select(LLMConfig).where(LLMConfig.is_default == True))
                llm_config = r.scalars().first()
            except Exception:
                pass

            # Get all documents with status "done"
            doc_result = await db.execute(
                select(Document).where(Document.kb_id == kb_id, Document.parse_status == "done")
            )
            docs = doc_result.scalars().all()

            embedder = get_embedder(kb.embedding_model, settings.EMBEDDING_DEVICE)
            vector_store.create_collection(kb_id, dense_dim=embedder.dim, force=True)

            total_chunks_done = 0
            total_chunks_overall = 0

            for doc in docs:
                chunk_result = await db.execute(
                    select(Chunk).where(Chunk.doc_id == doc.id).order_by(Chunk.chunk_index)
                )
                chunks = chunk_result.scalars().all()
                if not chunks:
                    continue

                total_chunks_overall += len(chunks)
                chunk_count = len(chunks)

                yield _sse("progress", {
                    "phase": "chunks",
                    "current": doc.filename,
                    "chunk_index": 0,
                    "total_chunks": chunk_count,
                    "message": f"正在处理: {doc.filename}",
                })

                # Embed and insert in batches
                batch = 10
                for i in range(0, chunk_count, batch):
                    batch_chunks = chunks[i:i + batch]
                    texts = [c.content for c in batch_chunks]
                    embs = embedder.embed_documents(texts)

                    dense_vecs = [embs["dense"][j].tolist() if hasattr(embs["dense"][j], 'tolist') else embs["dense"][j] for j in range(len(texts))]
                    sparse_list = embs.get("sparse")

                    import uuid
                    data = []
                    for j, bc in enumerate(batch_chunks):
                        data.append({
                            "id": str(uuid.uuid4()),
                            "chunk_id": str(bc.id),
                            "doc_id": str(doc.id),
                            "dense_vector": dense_vecs[j],
                            "sparse_vector": "" if sparse_list is None else json.dumps(sparse_list[j], default=str),
                            "content": bc.content[:8000],
                        })

                    # Insert (Milvus path)
                    if not vector_store._use_memory:
                        vector_store.client.insert(
                            collection_name=f"kb_{kb_id.replace('-', '_')}",
                            data=data,
                        )
                    else:
                        vector_store.client.insert(f"kb_{kb_id.replace('-', '_')}", data)

                    total_chunks_done += len(batch_chunks)
                    yield _sse("progress", {
                        "phase": "chunks",
                        "current": doc.filename,
                        "chunk_index": min(i + batch, chunk_count),
                        "total_chunks": chunk_count,
                        "overall_done": total_chunks_done,
                        "overall_total": total_chunks_overall,
                        "message": f"嵌入 {doc.filename}: {min(i+batch, chunk_count)}/{chunk_count}",
                    })

            # ── Graph re-embedding ──
            if graph_store.ready and llm_config:
                yield _sse("progress", {
                    "phase": "graph",
                    "current": "知识图谱实体",
                    "message": "正在嵌入图谱节点与边...",
                })

                all_nodes = graph_store.get_all_entities(kb_id)
                sub = graph_store.get_full_graph(kb_id, limit=5000)

                vector_result = await embed_graph_to_vector(
                    kb_id=kb_id,
                    nodes=all_nodes if all_nodes else sub.nodes,
                    edges=sub.edges if sub.edges else [],
                    embedding_model=kb.embedding_model,
                    force=True,
                )

                yield _sse("progress", {
                    "phase": "graph",
                    "message": f"图谱完成: {vector_result['nodes_embedded']}节点 {vector_result['edges_embedded']}边",
                    "nodes": vector_result["nodes_embedded"],
                    "edges": vector_result["edges_embedded"],
                })

            yield _sse("done", {
                "message": "重载完成",
                "chunks_embedded": total_chunks_done,
                "docs_processed": len(docs),
            })

    except Exception as e:
        logger.error(f"Reload vectors failed: {e}", exc_info=True)
        yield _sse("error", {"message": str(e)})


# ── Helpers ───────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _count_vectors(collection_name: str) -> int:
    if vector_store._use_memory:
        mem = vector_store.client
        if collection_name in mem.collections:
            return len(mem.collections[collection_name].get("vectors", []))
        return 0
    try:
        if vector_store.client and vector_store.client.has_collection(collection_name):
            # Milvus Lite: query with limit=0 to get total count, or use get_collection_stats
            try:
                stats = vector_store.client.get_collection_stats(collection_name)
                if isinstance(stats, dict):
                    return stats.get("row_count", 0)
            except Exception:
                pass
            # Fallback: count by querying all ids
            try:
                results = vector_store.client.query(
                    collection_name=collection_name,
                    filter="",
                    output_fields=["id"],
                    limit=100000,
                )
                return len(results)
            except Exception:
                pass
    except Exception:
        pass
    return 0


def _neo4j_rel_count(kb_id: str) -> int:
    sub = graph_store.get_full_graph(kb_id, limit=5000)
    return len(sub.edges)
