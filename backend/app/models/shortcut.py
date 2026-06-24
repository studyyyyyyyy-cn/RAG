"""Shortcut model — saved Q&A results for quick access."""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Shortcut(Base):
    __tablename__ = "shortcuts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    kb_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string of tags
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
