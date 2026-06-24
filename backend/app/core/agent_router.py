"""Agent router: intelligently routes queries to appropriate agents."""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retriever import retrieve, RetrievalResponse
from app.core.llm_manager import chat_completion, get_llm_config
from app.agents.base_agent import detect_intent
from app.agents.report_agent import report_agent
from app.agents.chart_agent import chart_agent
from app.agents.data_agent import data_agent
from app.agents.webpage_agent import webpage_agent
from app.utils.prompt_templates import build_rag_messages
from app.models.llm_config import LLMConfig

logger = logging.getLogger(__name__)

# Agent registry
AGENTS = {
    "report": report_agent,
    "chart": chart_agent,
    "data_table": data_agent,
    "webpage": webpage_agent,
}


async def route_and_generate(
    query: str,
    kb_id: str,
    db: AsyncSession,
    llm_config_id: str | None = None,
    conversation_history: list[dict] | None = None,
    stream: bool = True,
    enable_agent: bool = True,
) -> dict | AsyncGenerator[dict, None]:
    """Route query to appropriate handler based on intent detection.
    
    Args:
        query: User's question
        kb_id: Knowledge base ID
        db: Database session
        llm_config_id: Optional LLM config ID
        conversation_history: Previous messages
        stream: Whether to stream response
        enable_agent: Whether to enable agent routing (default True)
    
    Returns:
        If stream=False: dict with answer, citations, confidence
        If stream=True: async generator yielding partial response dicts
    """
    # 1. Retrieve relevant chunks
    retrieval = await retrieve(query=query, kb_id=kb_id, db=db)
    
    # 2. Get LLM config
    llm_config = await get_llm_config(db, llm_config_id)
    if not llm_config:
        raise ValueError("No LLM configured. Please add an LLM provider in settings.")
    
    # 3. Build context chunks
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
    
    # 4. Detect intent and route to appropriate agent (if enabled)
    intent = "text"  # Default
    if enable_agent:
        try:
            intent = await detect_intent(query, llm_config)
            logger.info(f"Detected intent: {intent} for query: {query[:50]}...")
        except Exception as e:
            logger.warning(f"Intent detection failed, using text mode: {e}")
    
    # 5. Route to appropriate handler
    if intent != "text" and intent in AGENTS:
        logger.info(f"Routing to {intent} agent")
        agent = AGENTS[intent]
        try:
            result = await agent.execute(query, context_chunks, llm_config)
            return {
                **result,
                "confidence": round(retrieval.confidence, 3),
                "confidence_label": retrieval.confidence_label,
                "metadata": {
                    "model_used": llm_config.model_name,
                    "retrieval_count": len(retrieval.results),
                    "agent_type": intent,
                },
            }
        except Exception as e:
            logger.error(f"Agent execution failed: {e}, falling back to text mode")
            intent = "text"  # Fallback to text mode
    
    # 6. Default: text mode
    messages = build_rag_messages(
        query=query,
        context_chunks=context_chunks,
        confidence=retrieval.confidence,
        confidence_label=retrieval.confidence_label,
        conversation_history=conversation_history,
    )
    
    if stream:
        from app.core.generator import _stream_answer  # lazy import to break circular dependency
        return _stream_answer(messages, llm_config, citations, retrieval, intent)
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
            "metadata": {
                "model_used": llm_config.model_name,
                "retrieval_count": len(retrieval.results),
                "agent_type": intent,
            },
        }
