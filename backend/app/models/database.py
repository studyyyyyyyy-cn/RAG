"""Database connection and session management."""

import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Ensure data directory exists for SQLite
if "sqlite" in settings.DATABASE_URL:
    db_path = settings.DATABASE_URL.split("///")[-1]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

# SQLite doesn't support pool_size/max_overflow
engine_kwargs = {"echo": settings.DATABASE_ECHO}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup (for development)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_lightweight_migrations)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI endpoints to get a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _run_lightweight_migrations(sync_conn):
    """Apply additive schema changes for local/dev databases."""
    inspector = inspect(sync_conn)

    if "documents" in inspector.get_table_names():
        doc_columns = {column["name"] for column in inspector.get_columns("documents")}
        if "chunk_progress" not in doc_columns:
            sync_conn.execute(text("ALTER TABLE documents ADD COLUMN chunk_progress INTEGER DEFAULT 0"))

    if "chunks" in inspector.get_table_names():
        chunk_columns = {column["name"] for column in inspector.get_columns("chunks")}
        if "metadata" not in chunk_columns:
            sync_conn.execute(text("ALTER TABLE chunks ADD COLUMN metadata TEXT"))
        if "keywords" not in chunk_columns:
            sync_conn.execute(text("ALTER TABLE chunks ADD COLUMN keywords TEXT"))
        if "questions" not in chunk_columns:
            sync_conn.execute(text("ALTER TABLE chunks ADD COLUMN questions TEXT"))
