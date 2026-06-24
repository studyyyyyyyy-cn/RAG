"""Shortcut API — save, list, delete, refresh Q&A results."""
import io
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.shortcut import Shortcut
from app.core.generator import generate_answer

router = APIRouter()


def html_to_md(html: str) -> str:
    """Convert HTML to Markdown."""
    import re
    import html as html_escape

    text = html_escape.unescape(html)

    # 处理表格
    def process_table(table_html):
        rows = re.findall(r'<tr>(.*?)</tr>', table_html)
        md_rows = []
        for i, row in enumerate(rows):
            cells = re.findall(r'<t[dh]>(.*?)</t[dh]>', row)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if i == 0:
                md_rows.append('| ' + ' | '.join(cells) + ' |')
                md_rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
            else:
                md_rows.append('| ' + ' | '.join(cells) + ' |')
        return '\n'.join(md_rows)

    # 处理表格 - 使用(?s)代替flags=re.DOTALL
    text = re.sub(r'(?s)<table>(.*?)</table>', lambda m: '\n\n' + process_table(m.group(1)) + '\n\n', text)

    # 处理标题
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', text)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', text)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', text)

    # 处理段落
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text)

    # 处理换行
    text = re.sub(r'<br\s*/?>', '\n', text)

    # 处理列表
    text = re.sub(r'<li>(.*?)</li>', r'- \1\n', text)
    text = re.sub(r'<ul[^>]*>|</ul>', '\n', text)
    text = re.sub(r'<ol[^>]*>|</ol>', '\n', text)

    # 移除剩余标签
    text = re.sub(r'<[^>]+>', '', text)

    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


def _deserialize_tags(tags: str | list | None) -> list[str] | None:
    """Deserialize tags from JSON string to list if needed."""
    if tags is None:
        return None
    if isinstance(tags, list):
        return tags
    if isinstance(tags, str):
        try:
            return json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            return [tags]  # fallback: single tag as list
    return None


@router.get("/shortcuts/{shortcut_id}/export-md")
async def export_shortcut_md(
    shortcut_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export a shortcut's report as Markdown."""
    import re
    import io
    import logging
    from datetime import datetime

    logger = logging.getLogger(__name__)

    try:
        shortcut = await db.get(Shortcut, shortcut_id)
        if not shortcut:
            raise HTTPException(status_code=404, detail="Shortcut not found")

        if not isinstance(shortcut.answer_snapshot, dict):
            raise HTTPException(status_code=400, detail="Invalid answer snapshot format")

        html_content = shortcut.answer_snapshot.get("html_content")
        if not html_content:
            raise HTTPException(status_code=400, detail="No HTML content to export")

        # Extract title from HTML or use default
        title_match = re.search(r'<h[1-2][^>]*>([^<]+)</h[1-2]>', html_content)
        title = title_match.group(1) if title_match else shortcut.title

        # Convert HTML to Markdown
        md_content = html_to_md(html_content)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\u4e00-\u9fa5]', '_', title)[:50]
        filename = f"{safe_title}_{timestamp}.md"

        return StreamingResponse(
            io.BytesIO(md_content.encode('utf-8')),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export MD error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


class ShortcutCreate(BaseModel):
    title: str
    query_text: str
    answer_snapshot: dict
    kb_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    tags: list[str] | None = None


class ShortcutUpdate(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    is_pinned: bool | None = None


@router.post("/shortcuts")
async def create_shortcut(
    data: ShortcutCreate,
    db: AsyncSession = Depends(get_db),
):
    """Save a Q&A result as a shortcut for quick access."""
    shortcut = Shortcut(
        title=data.title,
        query_text=data.query_text,
        answer_snapshot=data.answer_snapshot,
        kb_id=data.kb_id,
        conversation_id=data.conversation_id,
        message_id=data.message_id,
        tags=json.dumps(data.tags, ensure_ascii=False) if data.tags else None,
    )
    db.add(shortcut)
    await db.flush()

    return {
        "id": str(shortcut.id),
        "title": shortcut.title,
        "created_at": shortcut.created_at.isoformat() if shortcut.created_at else None,
    }


@router.get("/shortcuts")
async def list_shortcuts(
    tag: str | None = None,
    search: str | None = None,
    pinned_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List saved shortcuts with filtering."""
    query = select(Shortcut)
    count_query = select(func.count()).select_from(Shortcut)

    if pinned_only:
        query = query.where(Shortcut.is_pinned == True)
        count_query = count_query.where(Shortcut.is_pinned == True)

    if tag:
        # tags stored as JSON string, use LIKE for filtering
        query = query.where(Shortcut.tags.contains(tag))
        count_query = count_query.where(Shortcut.tags.contains(tag))

    if search:
        query = query.where(
            Shortcut.title.ilike(f"%{search}%") | Shortcut.query_text.ilike(f"%{search}%")
        )
        count_query = count_query.where(
            Shortcut.title.ilike(f"%{search}%") | Shortcut.query_text.ilike(f"%{search}%")
        )

    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Shortcut.is_pinned.desc(), Shortcut.created_at.desc())
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    shortcuts = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(s.id),
                "title": s.title,
                "query_text": s.query_text,
                "answer_snapshot": s.answer_snapshot,
                "kb_id": str(s.kb_id) if s.kb_id else None,
                "tags": _deserialize_tags(s.tags),
                "is_pinned": s.is_pinned,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_viewed_at": s.last_viewed_at.isoformat() if s.last_viewed_at else None,
            }
            for s in shortcuts
        ],
    }


@router.get("/shortcuts/{shortcut_id}")
async def get_shortcut(
    shortcut_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a shortcut and mark as viewed."""
    shortcut = await db.get(Shortcut, shortcut_id)
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    shortcut.last_viewed_at = datetime.now(timezone.utc)

    return {
        "id": str(shortcut.id),
        "title": shortcut.title,
        "query_text": shortcut.query_text,
        "answer_snapshot": shortcut.answer_snapshot,
        "kb_id": str(shortcut.kb_id) if shortcut.kb_id else None,
        "tags": _deserialize_tags(shortcut.tags),
        "is_pinned": shortcut.is_pinned,
        "created_at": shortcut.created_at.isoformat() if shortcut.created_at else None,
    }


@router.put("/shortcuts/{shortcut_id}")
async def update_shortcut(
    shortcut_id: str,
    data: ShortcutUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update shortcut title, tags, or pin status."""
    shortcut = await db.get(Shortcut, shortcut_id)
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(shortcut, key, value)

    return {"detail": "Updated"}


@router.delete("/shortcuts/{shortcut_id}")
async def delete_shortcut(
    shortcut_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a shortcut."""
    shortcut = await db.get(Shortcut, shortcut_id)
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    await db.delete(shortcut)
    return {"detail": "Deleted"}


@router.post("/shortcuts/{shortcut_id}/refresh")
async def refresh_shortcut(
    shortcut_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-execute the original query to get fresh results."""
    shortcut = await db.get(Shortcut, shortcut_id)
    if not shortcut:
        raise HTTPException(status_code=404, detail="Shortcut not found")

    if not shortcut.kb_id:
        raise HTTPException(status_code=400, detail="No knowledge base linked to this shortcut")

    # Re-run the query
    answer = await generate_answer(
        query=shortcut.query_text,
        kb_id=str(shortcut.kb_id),
        db=db,
        stream=False,
    )

    # Update snapshot
    shortcut.answer_snapshot = answer
    shortcut.last_viewed_at = datetime.now(timezone.utc)

    return {
        "id": str(shortcut.id),
        "answer_snapshot": answer,
        "refreshed": True,
    }
