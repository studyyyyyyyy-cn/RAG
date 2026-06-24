"""File upload handling utilities."""

import os
import uuid
from pathlib import Path

import aiofiles

from app.config import settings


async def save_upload_file(file_content: bytes, filename: str, kb_id: str) -> tuple[str, int]:
    """Save an uploaded file to disk.

    Returns (file_path, file_size).
    """
    # Create knowledge base upload directory
    kb_dir = Path(settings.UPLOAD_DIR) / str(kb_id)
    kb_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename to avoid collisions
    ext = Path(filename).suffix
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = kb_dir / unique_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    return str(file_path), len(file_content)


def get_file_extension(filename: str) -> str:
    """Extract and validate file extension."""
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {settings.ALLOWED_EXTENSIONS}")
    return ext


def delete_file(file_path: str):
    """Delete a file from disk."""
    if os.path.exists(file_path):
        os.remove(file_path)
