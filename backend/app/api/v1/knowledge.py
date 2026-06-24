"""Knowledge base CRUD API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.knowledge_base import KnowledgeBase
from app.core.vector_store import vector_store
from app.core.embedder import get_embedder
from app.config import settings

router = APIRouter()


class KBCreate(BaseModel):
    name: str
    description: str | None = None
    embedding_model: str = ""  # empty = use settings.DEFAULT_EMBEDDING_MODEL
    chunk_size: int = 512
    chunk_overlap: int = 64


class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    embedding_model: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    status: str | None = None


@router.post("/kb")
async def create_knowledge_base(
    data: KBCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base."""
    # Resolve embedding model: form default → settings default
    model_name = data.embedding_model or settings.DEFAULT_EMBEDDING_MODEL
    kb = KnowledgeBase(
        name=data.name,
        description=data.description,
        embedding_model=model_name,
        chunk_size=data.chunk_size,
        chunk_overlap=data.chunk_overlap,
    )
    db.add(kb)
    await db.flush()

    # Create Milvus collection with correct embedding dimension
    try:
        embedder = get_embedder(model_name, settings.EMBEDDING_DEVICE)
        dim = embedder.dim
    except Exception:
        dim = vector_store.DENSE_DIM  # fallback to default
    vector_store.create_collection(str(kb.id), dense_dim=dim)

    return {
        "id": str(kb.id),
        "name": kb.name,
        "description": kb.description,
        "embedding_model": kb.embedding_model,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "status": kb.status,
    }


@router.get("/kb")
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge bases."""
    total = (await db.execute(select(func.count()).select_from(KnowledgeBase))).scalar()
    result = await db.execute(
        select(KnowledgeBase)
        .order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    kbs = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "chunk_size": kb.chunk_size,
                "chunk_overlap": kb.chunk_overlap,
                "doc_count": kb.doc_count,
                "status": kb.status,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
            }
            for kb in kbs
        ],
    }


@router.get("/kb/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge base details."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    return {
        "id": str(kb.id),
        "name": kb.name,
        "description": kb.description,
        "embedding_model": kb.embedding_model,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "doc_count": kb.doc_count,
        "status": kb.status,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }


@router.put("/kb/{kb_id}")
async def update_knowledge_base(
    kb_id: str,
    data: KBUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update knowledge base settings."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(kb, key, value)

    return {"detail": "Updated", "id": str(kb.id)}


@router.delete("/kb/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge base and all its data."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Delete from DB first (cascades to documents, chunks, conversations)
    await db.delete(kb)
    await db.flush()

    # Then drop Milvus collection (if DB delete fails, Milvus stays intact)
    vector_store.drop_collection(str(kb_id))

    return {"detail": "Knowledge base deleted"}


@router.post("/kb/{kb_id}/repair-collection")
async def repair_collection(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Force-recreate the Milvus collection with correct embedding dimension.

    Use this when you get 'dimension mismatch' errors during chunking.
    Existing vectors will be lost — re-chunk documents after repair.
    """
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    embedder = get_embedder(kb.embedding_model, settings.EMBEDDING_DEVICE)
    correct_dim = embedder.dim
    old_dim = vector_store._get_collection_dim(vector_store._collection_name(kb_id))

    vector_store.create_collection(str(kb_id), dense_dim=correct_dim, force=True)

    return {
        "detail": "Collection repaired",
        "kb_id": kb_id,
        "embedding_model": kb.embedding_model,
        "correct_dim": correct_dim,
        "old_dim": old_dim,
        "hint": "请重新对文档执行分块操作",
    }
