"""Chat API endpoint with SSE support for text and structured agent outputs."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.conversation import Conversation, Message
from app.core.generator import generate_answer

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    kb_id: str
    conversation_id: str | None = None
    llm_config_id: str | None = None
    stream: bool = True
    enable_agent: bool = True


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a question and get a RAG-powered answer."""
    kb = await db.get(KnowledgeBase, req.kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    conversation = None
    conversation_history = None

    if req.conversation_id:
        conversation = await db.get(Conversation, req.conversation_id)

    if not conversation:
        conversation = Conversation(kb_id=kb.id, title=req.query[:100])
        db.add(conversation)
        await db.flush()

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(6)
    )
    history_msgs = list(reversed(history_result.scalars().all()))
    conversation_history = []
    for msg in history_msgs:
        text = msg.content.get("text", "") if isinstance(msg.content, dict) else str(msg.content)
        conversation_history.append({"role": msg.role, "content": text})

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content={"text": req.query},
    )
    db.add(user_msg)
    await db.commit()

    if req.stream:
        return StreamingResponse(
            _sse_stream(req, conversation.id, conversation_history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Conversation-Id": str(conversation.id),
            },
        )

    answer = await generate_answer(
        query=req.query,
        kb_id=req.kb_id,
        db=db,
        llm_config_id=req.llm_config_id,
        conversation_history=conversation_history,
        stream=False,
        enable_agent=req.enable_agent,
    )

    content = answer.get("content", {})
    chunk_ids = [c.get("chunk_id") for c in content.get("citations", []) if c.get("chunk_id")]
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        type=answer.get("type"),
        model_used=answer.get("metadata", {}).get("model_used"),
        confidence=answer.get("confidence"),
        retrieval_chunk_ids=json.dumps(chunk_ids) if chunk_ids else None,
    )
    db.add(assistant_msg)
    await db.commit()

    return {
        "conversation_id": str(conversation.id),
        "message_id": str(assistant_msg.id),
        "answer": answer,
    }


async def _sse_stream(req, conversation_id, conversation_history):
    """Generate SSE events for streaming response."""
    full_text = ""
    metadata = {}
    citations = []
    message_type = "text"
    message_content = {"text": "", "citations": []}

    try:
        async with async_session() as db:
            result = await generate_answer(
                query=req.query,
                kb_id=req.kb_id,
                db=db,
                llm_config_id=req.llm_config_id,
                conversation_history=conversation_history,
                stream=True,
                enable_agent=req.enable_agent,
            )

            # Structured agent results are returned as a dict even in "stream" mode.
            if not hasattr(result, "__aiter__"):
                answer = result
                content = answer.get("content", {})
                message_type = answer.get("type", "text")
                metadata = {
                    "confidence": answer.get("confidence"),
                    "confidence_label": answer.get("confidence_label"),
                    "model_used": answer.get("metadata", {}).get("model_used"),
                    "retrieval_count": answer.get("metadata", {}).get("retrieval_count"),
                    "citations": content.get("citations", []),
                    "agent_type": answer.get("metadata", {}).get("agent_type", message_type),
                }
                citations = metadata["citations"]
                message_content = content
                full_text = content.get("text", "")

                yield f"event: metadata\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                yield f"event: agent_result\ndata: {json.dumps({'type': message_type, 'content': content}, ensure_ascii=False)}\n\n"
            else:
                async for event in result:
                    event_type = event.get("event", "text_chunk")
                    data = event.get("data", {})

                    if event_type == "metadata":
                        metadata = data
                        citations = data.get("citations", [])
                        message_type = data.get("agent_type", "text")
                        message_content["citations"] = citations
                    elif event_type == "text_chunk":
                        full_text += data.get("text", "")
                    elif event_type == "done":
                        pass

                    yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                message_content = {"text": full_text, "citations": citations}

            chunk_ids = [c.get("chunk_id") for c in citations if c.get("chunk_id")]
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=message_content,
                type=message_type,
                model_used=metadata.get("model_used"),
                confidence=metadata.get("confidence"),
                retrieval_chunk_ids=json.dumps(chunk_ids) if chunk_ids else None,
            )
            db.add(assistant_msg)
            await db.commit()

            done_data = {
                "message_id": str(assistant_msg.id),
                "conversation_id": str(conversation_id),
            }
            yield f"event: complete\ndata: {json.dumps(done_data)}\n\n"

    except Exception as e:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.error(f"SSE stream error: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'detail': str(e), 'type': type(e).__name__})}\n\n"


@router.get("/conversations")
async def list_conversations(
    kb_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List conversations, optionally filtered by knowledge base."""
    from sqlalchemy import func

    query = select(Conversation).order_by(Conversation.updated_at.desc())
    count_query = select(func.count()).select_from(Conversation)

    if kb_id:
        query = query.where(Conversation.kb_id == kb_id)
        count_query = count_query.where(Conversation.kb_id == kb_id)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    convos = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(c.id),
                "kb_id": str(c.kb_id),
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in convos
        ],
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all its messages."""
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    return {
        "id": str(conversation.id),
        "kb_id": str(conversation.kb_id),
        "title": conversation.title,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "type": m.type,
                "model_used": m.model_used,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


class UpdateConversationRequest(BaseModel):
    title: str | None = None


@router.put("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update conversation title."""
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        conversation.title = req.title[:100]

    await db.commit()

    return {
        "id": str(conversation.id),
        "title": conversation.title,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
    )
    messages = result.scalars().all()
    for msg in messages:
        await db.delete(msg)

    await db.delete(conversation)
    await db.commit()

    return {"detail": "Conversation deleted"}


def html_to_md(html: str) -> str:
    """Convert HTML to Markdown."""
    import re
    import html as html_escape

    text = html_escape.unescape(html)

    def process_table(table_html):
        rows = re.findall(r"<tr>(.*?)</tr>", table_html)
        md_rows = []
        for i, row in enumerate(rows):
            cells = re.findall(r"<t[dh]>(.*?)</t[dh]>", row)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if i == 0:
                md_rows.append("| " + " | ".join(cells) + " |")
                md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
            else:
                md_rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(md_rows)

    text = re.sub(r"(?s)<table>(.*?)</table>", lambda m: "\n\n" + process_table(m.group(1)) + "\n\n", text)
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n\n", text)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n\n", text)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n\n", text)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<li>(.*?)</li>", r"- \1\n", text)
    text = re.sub(r"<ul[^>]*>|</ul>", "\n", text)
    text = re.sub(r"<ol[^>]*>|</ol>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@router.get("/messages/{message_id}/export-md")
async def export_message_md(
    message_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export a message's HTML content as Markdown."""
    import io
    import logging
    import re
    from datetime import datetime

    logger = logging.getLogger(__name__)

    try:
        message = await db.get(Message, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if not isinstance(message.content, dict):
            raise HTTPException(status_code=400, detail="Invalid message content format")

        html_content = message.content.get("html_content")
        if not html_content:
            raise HTTPException(status_code=400, detail="No HTML content to export")

        title_match = re.search(r"<h[1-2][^>]*>([^<]+)</h[1-2]>", html_content)
        title = title_match.group(1) if title_match else "Report"
        md_content = html_to_md(html_content)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r"[^\w\u4e00-\u9fa5]", "_", title)[:50]
        filename = f"{safe_title}_{timestamp}.md"

        return StreamingResponse(
            io.BytesIO(md_content.encode("utf-8")),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export MD error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
