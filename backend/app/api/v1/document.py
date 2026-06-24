"""Document upload and management API endpoints."""
import asyncio
import json
import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.chunker import ChunkMethod, get_chunker
from app.core.document_parser import document_parser
from app.core.embedder import get_embedder
from app.core.exceptions import (
    ChunkError, EmptyDocumentError, DimensionMismatchError,
    VectorInsertError, VectorSearchError, GraphBuildError,
)
from app.core.llm_manager import chat_completion, get_llm_config
from app.core.vector_store import vector_store
from app.models.chunk import Chunk
from app.models.database import get_db
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.utils.file_handler import delete_file, get_file_extension, save_upload_file
from app.utils.prompt_templates import build_rag_messages

router = APIRouter()
logger = logging.getLogger(__name__)


class ChunkBatchRequest(BaseModel):
    doc_ids: list[str]
    chunk_method: ChunkMethod
    params: dict | None = None


class TestChatRequest(BaseModel):
    query: str
    doc_id: str | None = None
    top_k: int = 5
    enable_rerank: bool = True
    debug: bool = True


def _extract_keywords(text: str, top_k: int = 5) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", text[:5000])
    freq: dict[str, int] = {}
    for word in words:
        token = word.lower()
        freq[token] = freq.get(token, 0) + 1
    return [word for word, _ in sorted(freq.items(), key=lambda item: item[1], reverse=True)[:top_k]]


def _generate_questions(text: str, count: int = 3) -> list[str]:
    sentences = [s.strip() for s in re.split(r"[。！？!?\.]+", text[:2000]) if len(s.strip()) > 10]
    questions = []

    for sentence in sentences[:count]:
        preview = sentence[:30]
        if "如何" in sentence or "怎么" in sentence:
            questions.append(f"{preview} 的具体做法是什么？")
        elif "是" in sentence or "为" in sentence:
            questions.append(f"{preview} 具体指的是什么？")
        else:
            questions.append(f"这段内容中提到的“{preview}”是什么意思？")

    while len(questions) < count:
        questions.append("这段内容的核心观点是什么？")

    return questions[:count]


def _map_chunk_status(parse_status: str) -> str:
    if parse_status == "done":
        return "chunked"
    if parse_status == "chunking":
        return "chunking"
    return "not_chunked"


async def _refresh_doc_count(kb_id: str, db: AsyncSession):
    count_result = await db.execute(
        select(func.count()).where(Document.kb_id == kb_id, Document.parse_status == "done")
    )
    kb = await db.get(KnowledgeBase, kb_id)
    if kb:
        kb.doc_count = count_result.scalar() or 0


async def _parse_document(doc: Document):
    pages = document_parser.parse(doc.file_path)
    if not pages:
        raise EmptyDocumentError(doc.filename)


async def _process_document(
    doc: Document,
    kb: KnowledgeBase,
    chunk_method: str,
    db: AsyncSession,
    params: dict | None = None,
):
    params = params or {}
    keyword_count = int(params.get("keyword_count", 5))
    question_count = int(params.get("question_count", 3))
    chunk_size = int(params.get("chunk_size", kb.chunk_size))
    chunk_overlap = int(params.get("overlap", kb.chunk_overlap))

    doc.chunk_progress = 10
    await db.flush()

    pages = document_parser.parse(doc.file_path)
    if not pages:
        raise EmptyDocumentError(doc.filename)

    chunker = get_chunker(
        method=chunk_method,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    doc.chunk_progress = 30
    await db.flush()

    if chunk_method == "parent_child":
        child_chunks, parent_chunks = chunker.chunk_pages(pages)
    else:
        child_chunks = chunker.chunk_pages(pages)
        parent_chunks = []

    if not child_chunks:
        raise ChunkError("未生成任何分块，请检查文档内容或换一种分块策略")

    doc.chunk_progress = 45
    await db.flush()

    await db.execute(delete(Chunk).where(Chunk.doc_id == doc.id))
    vector_store.delete_by_doc(str(kb.id), str(doc.id))

    embedder = get_embedder(kb.embedding_model, settings.EMBEDDING_DEVICE)
    texts = [chunk.text for chunk in child_chunks]
    embeddings = embedder.embed_documents(texts)
    doc.chunk_progress = 60
    await db.flush()

    logger.info(f"Using embedder: {kb.embedding_model}, dim={embedder.dim}, device={settings.EMBEDDING_DEVICE}")
    logger.info(f"Dense vectors shape: {embeddings['dense'].shape if hasattr(embeddings['dense'], 'shape') else len(embeddings['dense'])}")
    vector_store.create_collection(str(kb.id), dense_dim=embedder.dim)

    parent_chunk_map: dict[int, str] = {}
    for parent_chunk in parent_chunks:
        chunk_record = Chunk(
            doc_id=doc.id,
            kb_id=kb.id,
            content=parent_chunk.text,
            chunk_index=parent_chunk.chunk_index,
            page_number=parent_chunk.page_number,
            section_title=parent_chunk.section_title,
            token_count=parent_chunk.token_count,
            chunk_metadata=json.dumps(parent_chunk.metadata, ensure_ascii=False) if parent_chunk.metadata else None,
            keywords=json.dumps(_extract_keywords(parent_chunk.text, keyword_count), ensure_ascii=False),
            questions=json.dumps(_generate_questions(parent_chunk.text, question_count), ensure_ascii=False),
        )
        db.add(chunk_record)
        await db.flush()
        parent_chunk_map[parent_chunk.chunk_index] = chunk_record.id

    chunk_ids: list[str] = []
    doc_ids: list[str] = []
    contents: list[str] = []
    dense_vectors = []
    sparse_vectors = []

    for index, child_chunk in enumerate(child_chunks):
        parent_id = parent_chunk_map.get(child_chunk.parent_chunk_index) if child_chunk.parent_chunk_index is not None else None
        chunk_record = Chunk(
            doc_id=doc.id,
            kb_id=kb.id,
            content=child_chunk.text,
            chunk_index=child_chunk.chunk_index,
            parent_chunk_id=parent_id,
            page_number=child_chunk.page_number,
            section_title=child_chunk.section_title,
            token_count=child_chunk.token_count,
            chunk_metadata=json.dumps(child_chunk.metadata, ensure_ascii=False) if child_chunk.metadata else None,
            keywords=json.dumps(_extract_keywords(child_chunk.text, keyword_count), ensure_ascii=False),
            questions=json.dumps(_generate_questions(child_chunk.text, question_count), ensure_ascii=False),
        )
        db.add(chunk_record)
        await db.flush()

        chunk_ids.append(str(chunk_record.id))
        doc_ids.append(str(doc.id))
        contents.append(child_chunk.text)
        dense_vectors.append(embeddings["dense"][index])
        if "sparse" in embeddings:
            sparse_vectors.append(embeddings["sparse"][index])

    doc.chunk_progress = 85
    await db.flush()

    try:
        vector_store.insert(
            kb_id=str(kb.id),
            chunk_ids=chunk_ids,
            doc_ids=doc_ids,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors if sparse_vectors else None,
            contents=contents,
        )
    except VectorInsertError as e:
        error_msg = str(e)
        if "DataNotMatch" in error_msg or "inconsistent" in error_msg.lower() or "dim" in error_msg.lower():
            logger.warning(f"Schema/dimension mismatch, auto-repairing: {error_msg}")
            vector_store.create_collection(str(kb.id), dense_dim=embedder.dim, force=True)
            vector_store.insert(
                kb_id=str(kb.id),
                chunk_ids=chunk_ids,
                doc_ids=doc_ids,
                dense_vectors=dense_vectors,
                sparse_vectors=sparse_vectors if sparse_vectors else None,
                contents=contents,
            )
        else:
            raise

    doc.total_chunks = len(child_chunks)
    doc.chunk_progress = 100
    await db.flush()

    # Build knowledge graph (async, non-blocking)
    try:
        from app.core.graph_builder import build_graph_for_document
        llm_cfg = await get_llm_config(db, None)
        if llm_cfg:
            graph_result = await build_graph_for_document(
                doc_id=str(doc.id),
                kb_id=str(kb.id),
                db=db,
                llm_config=llm_cfg,
            )
            logger.info(f"Graph built for doc {doc.id}: {graph_result}")
    except Exception as e:
        logger.warning(f"Graph build skipped for doc {doc.id}: {e}")


@router.post("/kb/{kb_id}/documents")
async def upload_documents(
    kb_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more documents to a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    results = []
    for file in files:
        try:
            ext = get_file_extension(file.filename)
            content = await file.read()

            if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                results.append({"filename": file.filename, "status": "error", "detail": "File too large"})
                continue

            file_path, file_size = await save_upload_file(content, file.filename, str(kb_id))
            doc = Document(
                kb_id=kb_id,
                filename=file.filename,
                file_type=ext,
                file_size=file_size,
                file_path=file_path,
                parse_status="parsing",
                chunk_progress=0,
            )
            db.add(doc)
            await db.flush()

            try:
                await _parse_document(doc)
                doc.parse_status = "parsed"
            except Exception as e:
                doc.parse_status = "failed"
                doc.error_message = str(e)

            results.append({
                "id": str(doc.id),
                "filename": file.filename,
                "name": file.filename,
                "status": doc.parse_status,
                "error_message": doc.error_message,
            })
        except ValueError as e:
            results.append({"filename": file.filename, "status": "error", "detail": str(e)})

    await _refresh_doc_count(kb_id, db)
    return {"uploaded": len(results), "results": results}


@router.post("/kb/{kb_id}/documents/{doc_id}/chunk")
async def chunk_document(
    kb_id: str,
    doc_id: str,
    chunk_method: ChunkMethod = Query(..., description="Chunking method"),
    db: AsyncSession = Depends(get_db),
):
    """Execute chunking on a parsed document."""
    doc = await db.get(Document, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.parse_status not in ["parsed", "failed"]:
        raise HTTPException(status_code=400, detail=f"Document status is {doc.parse_status}, must be 'parsed'")

    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    doc.parse_status = "chunking"
    doc.chunk_method = chunk_method
    doc.chunk_progress = 0
    await db.commit()

    try:
        await _process_document(doc, kb, chunk_method, db)
        doc.parse_status = "done"
        await _refresh_doc_count(kb_id, db)
        await db.commit()
        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.parse_status,
            "chunk_status": _map_chunk_status(doc.parse_status),
            "chunk_method": doc.chunk_method,
            "total_chunks": doc.total_chunks,
            "progress": doc.chunk_progress,
        }
    except Exception as e:
        doc.parse_status = "failed"
        doc.chunk_progress = 0
        doc.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/{kb_id}/build-graph")
async def build_knowledge_graph(
    kb_id: str,
    doc_ids: list[str] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Build knowledge graph for existing documents in a knowledge base.

    If doc_ids is provided, only build graph for those documents.
    Otherwise build graph for all 'done' documents.
    """
    from app.core.graph_builder import build_graph_for_kb, build_graph_for_document

    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    llm_config = await get_llm_config(db, None)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM configured — graph extraction requires LLM")

    if doc_ids:
        results = []
        for doc_id in doc_ids:
            doc = await db.get(Document, doc_id)
            if not doc or doc.kb_id != kb_id:
                results.append({"doc_id": doc_id, "status": "skipped", "reason": "not found"})
                continue
            result = await build_graph_for_document(doc_id, kb_id, db, llm_config)
            results.append({"doc_id": doc_id, **result})
        return {"status": "done", "results": results}
    else:
        result = await build_graph_for_kb(kb_id, db, llm_config)
        return result


@router.post("/kb/{kb_id}/documents/chunk-batch")
async def chunk_documents_batch(
    kb_id: str,
    request: ChunkBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute chunking on multiple documents in sequence."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    results = []
    for doc_id in request.doc_ids:
        doc = await db.get(Document, doc_id)
        if not doc or doc.kb_id != kb_id:
            results.append({"id": doc_id, "document_id": doc_id, "status": "error", "success": False, "detail": "Document not found"})
            continue
        if doc.parse_status not in ["parsed", "failed"]:
            results.append({
                "id": doc_id,
                "document_id": doc_id,
                "status": "skipped",
                "success": False,
                "detail": f"Status is {doc.parse_status}, must be 'parsed'",
            })
            continue

        doc.parse_status = "chunking"
        doc.chunk_method = request.chunk_method
        doc.chunk_progress = 0
        await db.commit()

        try:
            await _process_document(doc, kb, request.chunk_method, db, request.params)
            doc.parse_status = "done"
            await db.commit()
            results.append({
                "id": str(doc.id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "status": "done",
                "success": True,
                "chunk_method": doc.chunk_method,
                "total_chunks": doc.total_chunks,
            })
        except Exception as e:
            doc.parse_status = "failed"
            doc.chunk_progress = 0
            doc.error_message = str(e)
            await db.commit()
            results.append({
                "id": str(doc.id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "status": "failed",
                "success": False,
                "error_message": str(e),
            })

    await _refresh_doc_count(kb_id, db)
    return {"processed": len(results), "results": results}


@router.get("/kb/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List documents in a knowledge base."""
    offset = (page - 1) * page_size
    count_result = await db.execute(select(func.count()).where(Document.kb_id == kb_id))
    total = count_result.scalar()
    result = await db.execute(
        select(Document)
        .where(Document.kb_id == kb_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    docs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "name": doc.filename,
                "file_type": doc.file_type,
                "file_format": doc.file_type,
                "file_size": doc.file_size,
                "total_chunks": doc.total_chunks,
                "chunk_count": doc.total_chunks,
                "parse_status": doc.parse_status,
                "chunk_status": _map_chunk_status(doc.parse_status),
                "chunk_method": doc.chunk_method,
                "chunk_progress": doc.chunk_progress,
                "error_message": doc.error_message,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "upload_time": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in docs
        ],
    }


@router.delete("/kb/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks/vectors."""
    doc = await db.get(Document, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_by_doc(str(kb_id), str(doc_id))
    delete_file(doc.file_path)
    await db.delete(doc)
    await _refresh_doc_count(kb_id, db)
    return {"detail": "Document deleted"}


@router.get("/kb/{kb_id}/documents/{doc_id}/status")
async def document_status(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check document parse/chunk status."""
    doc = await db.get(Document, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": str(doc.id),
        "parse_status": doc.parse_status,
        "status": _map_chunk_status(doc.parse_status),
        "progress": doc.chunk_progress,
        "total_chunks": doc.total_chunks,
        "error_message": doc.error_message,
    }


@router.get("/kb/{kb_id}/documents/{doc_id}/chunks")
async def list_document_chunks(
    kb_id: str,
    doc_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List chunks of a document."""
    doc = await db.get(Document, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Document not found")

    offset = (page - 1) * page_size
    if doc.chunk_method == "parent_child":
        count_result = await db.execute(
            select(func.count()).where(Chunk.doc_id == doc_id, Chunk.parent_chunk_id.is_not(None))
        )
        total = count_result.scalar()
        result = await db.execute(
            select(Chunk)
            .where(Chunk.doc_id == doc_id, Chunk.parent_chunk_id.is_not(None))
            .order_by(Chunk.chunk_index)
            .offset(offset)
            .limit(page_size)
        )
    else:
        count_result = await db.execute(select(func.count()).where(Chunk.doc_id == doc_id))
        total = count_result.scalar()
        result = await db.execute(
            select(Chunk)
            .where(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
            .offset(offset)
            .limit(page_size)
        )

    chunks = result.scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
                "metadata": chunk.chunk_metadata,
                "keywords": chunk.keywords,
                "questions": chunk.questions,
            }
            for chunk in chunks
        ],
    }


@router.get("/kb/{kb_id}/chunks/{chunk_id}")
async def get_chunk(
    kb_id: str,
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single chunk with parent context."""
    chunk = await db.get(Chunk, chunk_id)
    if not chunk or chunk.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="Chunk not found")

    parent_content = None
    if chunk.parent_chunk_id:
        parent = await db.get(Chunk, chunk.parent_chunk_id)
        if parent:
            parent_content = parent.content

    doc = await db.get(Document, chunk.doc_id)
    return {
        "id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "token_count": chunk.token_count,
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "parent_content": parent_content,
        "metadata": chunk.chunk_metadata,
        "keywords": chunk.keywords,
        "questions": chunk.questions,
        "document": {
            "id": str(doc.id),
            "filename": doc.filename,
        } if doc else None,
    }


@router.post("/kb/{kb_id}/test-chat")
async def test_chat(
    kb_id: str,
    request: TestChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Test RAG retrieval and answer generation against a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    debug_data = {
        "query": request.query,
        "rewritten_query": None,
        "retrieval_results": [],
        "reranked_results": [],
        "selected_chunks": [],
        "context_length": 0,
        "prompt_template": None,
        "answer": None,
        "confidence": 0.0,
        "confidence_label": "low",
        "sources": [],
        "metrics": {},
    }

    start_time = time.time()

    try:
        rewritten_query = None
        if len(request.query) > 50:
            llm_config = await get_llm_config(db, None)
            if llm_config:
                rewrite_messages = [{
                    "role": "user",
                    "content": (
                        "请将以下问题改写为更适合向量检索的简洁查询，保留关键词，去除冗余。"
                        f"\n\n{request.query}\n\n只返回改写后的查询。"
                    ),
                }]
                try:
                    rewritten_query = (await chat_completion(rewrite_messages, llm_config, stream=False)).strip()
                    debug_data["rewritten_query"] = rewritten_query
                except Exception:
                    rewritten_query = None

        search_query = rewritten_query or request.query
        retrieval_start = time.time()
        embedder = get_embedder(kb.embedding_model, settings.EMBEDDING_DEVICE)
        query_embedding = embedder.embed_query(search_query)
        search_results = vector_store.hybrid_search(
            kb_id=str(kb_id),
            dense_query=query_embedding["dense"],
            sparse_query=query_embedding.get("sparse"),
            top_k=request.top_k * 2,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000

        for result in search_results:
            chunk = await db.get(Chunk, result.chunk_id)
            if not chunk:
                continue
            if request.doc_id and str(chunk.doc_id) != request.doc_id:
                continue
            doc = await db.get(Document, chunk.doc_id)
            debug_data["retrieval_results"].append({
                "chunk_id": str(chunk.id),
                "content": chunk.content[:300] + ("..." if len(chunk.content) > 300 else ""),
                "dense_score": result.score,
                "sparse_score": None,
                "hybrid_score": result.score,
                "rerank_score": None,
                "document": doc.filename if doc else "Unknown",
                "page": chunk.page_number,
                "section": chunk.section_title,
            })

        rerank_start = time.time()
        if request.enable_rerank:
            selected_chunks = sorted(
                debug_data["retrieval_results"],
                key=lambda item: item["hybrid_score"],
                reverse=True,
            )[:request.top_k]
            for item in selected_chunks:
                item["rerank_score"] = item["hybrid_score"]
            debug_data["reranked_results"] = selected_chunks
        else:
            selected_chunks = debug_data["retrieval_results"][:request.top_k]
            debug_data["reranked_results"] = selected_chunks
        rerank_time = (time.time() - rerank_start) * 1000

        context_parts = []
        context_chunks = []
        for chunk_info in selected_chunks:
            chunk = await db.get(Chunk, chunk_info["chunk_id"])
            if not chunk:
                continue
            context_parts.append(chunk.content)
            context_chunks.append({
                "content": chunk.content,
                "parent_content": None,
                "source": chunk_info["document"],
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
            })

        context = "\n\n".join(context_parts)
        context_length = len(context.split())
        debug_data["selected_chunks"] = selected_chunks
        debug_data["context_length"] = context_length

        avg_score = 0.0
        confidence_label = "low"
        if selected_chunks:
            avg_score = sum(item["hybrid_score"] for item in selected_chunks) / len(selected_chunks)
            if avg_score >= 0.8:
                confidence_label = "high"
            elif avg_score >= 0.6:
                confidence_label = "medium"

        messages = build_rag_messages(
            query=request.query,
            context_chunks=context_chunks,
            confidence=avg_score,
            confidence_label=confidence_label,
            conversation_history=None,
        )
        debug_data["prompt_template"] = "\n\n".join(f"{item['role']}: {item['content']}" for item in messages)

        generation_start = time.time()
        llm_config = await get_llm_config(db, None)
        if not llm_config:
            raise HTTPException(status_code=500, detail="未配置 LLM，请先在设置中添加模型配置")
        answer_text = await chat_completion(messages, llm_config, stream=False)
        generation_time = (time.time() - generation_start) * 1000

        debug_data["answer"] = answer_text
        debug_data["confidence"] = avg_score
        debug_data["confidence_label"] = confidence_label
        debug_data["sources"] = [
            {
                "content": item["content"],
                "relevance": item["hybrid_score"],
                "page_number": item["page"],
                "section_title": item["section"],
            }
            for item in selected_chunks
        ]
        debug_data["metrics"] = {
            "retrieval_time_ms": round(retrieval_time, 2),
            "rerank_time_ms": round(rerank_time, 2),
            "generation_time_ms": round(generation_time, 2),
            "total_time_ms": round((time.time() - start_time) * 1000, 2),
            "input_tokens": context_length + len(request.query.split()),
            "output_tokens": len(answer_text.split()),
            "total_tokens": context_length + len(request.query.split()) + len(answer_text.split()),
        }
        return debug_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试问答失败: {str(e)}")
