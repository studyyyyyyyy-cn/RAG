"""Answer generator: orchestrates retrieval + LLM for RAG response."""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retriever import retrieve, RetrievalResponse
from app.core.llm_manager import chat_completion, get_llm_config
from app.core.agent_router import route_and_generate
from app.utils.prompt_templates import build_rag_messages
from app.models.llm_config import LLMConfig

logger = logging.getLogger(__name__)


def _count_graph_nodes(graph_context: str | None) -> int:
    """Roughly count entities from graph context text."""
    if not graph_context:
        return 0
    # Count lines with " - " pattern (entity relations)
    return graph_context.count("关联实体与关系")


def _count_graph_edges(graph_context: str | None) -> int:
    """Roughly count edges from graph context text."""
    if not graph_context:
        return 0
    return graph_context.count("  - ")


async def generate_answer(
    query: str,
    kb_id: str,
    db: AsyncSession,
    llm_config_id: str | None = None,
    conversation_history: list[dict] | None = None,
    stream: bool = True,
    enable_agent: bool = True,
) -> dict | AsyncGenerator[dict, None]:
    """Full RAG pipeline with intelligent agent routing.

    Args:
        query: User's question
        kb_id: Knowledge base ID
        db: Database session
        llm_config_id: Optional LLM config ID
        conversation_history: Previous messages for multi-turn context
        stream: Whether to stream response
        enable_agent: Whether to enable intelligent agent routing (default True)
    
    Returns:
        If stream=False: dict with answer, citations, confidence
        If stream=True: async generator yielding partial response dicts
    """
    # Use agent router when enabled
    if enable_agent:
        return await route_and_generate(
            query=query,
            kb_id=kb_id,
            db=db,
            llm_config_id=llm_config_id,
            conversation_history=conversation_history,
            stream=stream,
            enable_agent=True,
        )
    
    # Fallback: original text-only mode
    # 1. Retrieve relevant chunks
    retrieval = await retrieve(query=query, kb_id=kb_id, db=db)

    # 2. Get LLM config
    llm_config = await get_llm_config(db, llm_config_id)
    if not llm_config:
        raise ValueError("No LLM configured. Please add an LLM provider in settings.")

    # 3. Build context chunks for prompt
    context_chunks = []
    citations = []
    for r in retrieval.results:
        chunk_data = {
            "content": r.content,
            "parent_content": r.parent_content,
            "source": r.metadata.get("source", "未知文档"),
            "page_number": r.page_number,
            "section_title": r.section_title,
        }
        context_chunks.append(chunk_data)

        citations.append({
            "chunk_id": r.chunk_id,
            "doc_id": r.doc_id,
            "source": chunk_data["source"],
            "page_number": r.page_number,
            "section_title": r.section_title,
            "relevance": round(r.score, 3),
        })

    # 4. Build messages
    messages = build_rag_messages(
        query=query,
        context_chunks=context_chunks,
        confidence=retrieval.confidence,
        confidence_label=retrieval.confidence_label,
        conversation_history=conversation_history,
        graph_context=retrieval.graph_context,
        chunk_count=len(retrieval.results),
        graph_entity_count=_count_graph_nodes(retrieval.graph_context),
        graph_edge_count=_count_graph_edges(retrieval.graph_context),
    )

    # 5. Generate answer
    if stream:
        return _stream_answer(messages, llm_config, citations, retrieval)
    else:
        answer_text = await chat_completion(messages, llm_config, stream=False)
        return {
            "type": "text",
            "content": {
                "text": answer_text,
                "citations": citations,
            },
            "confidence": round(retrieval.confidence, 3),
            "confidence_label": retrieval.confidence_label,
            "graph_context": retrieval.graph_context,
            "metadata": {
                "model_used": llm_config.model_name,
                "retrieval_count": len(retrieval.results),
            },
        }


async def _stream_answer(
    messages: list[dict],
    llm_config: LLMConfig,
    citations: list[dict],
    retrieval: RetrievalResponse,
    intent: str = "text",
) -> AsyncGenerator[dict, None]:
    """Stream RAG answer with SSE-compatible chunks."""
    # First emit metadata
    yield {
        "event": "metadata",
        "data": {
            "confidence": round(retrieval.confidence, 3),
            "confidence_label": retrieval.confidence_label,
            "model_used": llm_config.model_name,
            "retrieval_count": len(retrieval.results),
            "citations": citations,
            "agent_type": intent,
        },
    }

    # Stream text chunks
    full_text = ""
    stream_gen = await chat_completion(messages, llm_config, stream=True)
    async for chunk in stream_gen:
        full_text += chunk
        yield {
            "event": "text_chunk",
            "data": {"text": chunk},
        }

    # Final event
    yield {
        "event": "done",
        "data": {
            "full_text": full_text,
            "type": intent,
        },
    }
