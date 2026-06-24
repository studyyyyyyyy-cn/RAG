"""Agent API endpoints — invoke specialized agents for multi-format output."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.conversation import Conversation, Message
from app.core.retriever import retrieve
from app.core.llm_manager import get_llm_config
from app.agents.base_agent import detect_intent
from app.agents.chart_agent import chart_agent
from app.agents.report_agent import report_agent
from app.agents.webpage_agent import webpage_agent
from app.agents.data_agent import data_agent

router = APIRouter()
logger = logging.getLogger(__name__)

AGENT_MAP = {
    "chart": chart_agent,
    "report": report_agent,
    "webpage": webpage_agent,
    "data_table": data_agent,
}


class AgentRequest(BaseModel):
    query: str
    kb_id: str
    agent_type: str | None = None  # auto-detect if None
    llm_config_id: str | None = None
    conversation_id: str | None = None


class IntentRequest(BaseModel):
    query: str
    llm_config_id: str | None = None


@router.post("/agent/detect-intent")
async def detect_agent_intent(
    req: IntentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Detect the best agent type for a query."""
    llm_config = await get_llm_config(db, req.llm_config_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM configured")

    agent_type = await detect_intent(req.query, llm_config)
    return {"agent_type": agent_type}


@router.post("/agent/execute")
async def execute_agent(
    req: AgentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a specialized agent for multi-format output.

    If agent_type is not specified, auto-detects the best format.
    """
    # Verify KB
    kb = await db.get(KnowledgeBase, req.kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Get LLM config
    llm_config = await get_llm_config(db, req.llm_config_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM configured")

    # Auto-detect intent if needed
    agent_type = req.agent_type
    if not agent_type or agent_type == "auto":
        agent_type = await detect_intent(req.query, llm_config)

    # If text type, redirect to normal chat
    if agent_type == "text":
        return {"type": "text", "redirect": "/api/v1/chat", "detail": "Use the chat endpoint for text responses"}

    # Get agent
    agent = AGENT_MAP.get(agent_type)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    # Get or create conversation
    conversation = None
    if req.conversation_id:
        conversation = await db.get(Conversation, req.conversation_id)

    if not conversation:
        conversation = Conversation(kb_id=kb.id, title=req.query[:100])
        db.add(conversation)
        await db.flush()

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content={"text": req.query},
    )
    db.add(user_msg)
    await db.commit()

    # Retrieve context
    retrieval = await retrieve(query=req.query, kb_id=req.kb_id, db=db)

    context = [
        {
            "content": r.content,
            "parent_content": r.parent_content,
            "source": r.metadata.get("source", "未知文档"),
            "page_number": r.page_number,
            "section_title": r.section_title,
        }
        for r in retrieval.results
    ]

    # Execute agent
    try:
        result = await agent.execute(req.query, context, llm_config)
    except Exception as e:
        logger.exception("Agent execution failed for type=%s query=%s", agent_type, req.query[:100])
        raise HTTPException(status_code=500, detail=f"{agent_type} agent failed: {str(e)}") from e
    result["confidence"] = round(retrieval.confidence, 3)
    result["confidence_label"] = retrieval.confidence_label

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("content", {}),
        type=result.get("type"),  # 保存消息类型（report/chart/webpage等）
        model_used=llm_config.model_name,
        confidence=result.get("confidence"),
    )
    db.add(assistant_msg)
    await db.commit()

    # Add conversation_id to response
    result["conversation_id"] = str(conversation.id)
    result["message_id"] = str(assistant_msg.id)

    return result


@router.post("/agent/chart")
async def generate_chart(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    """Shortcut to generate a chart."""
    req.agent_type = "chart"
    return await execute_agent(req, db)


@router.post("/agent/report")
async def generate_report(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    """Shortcut to generate a report."""
    req.agent_type = "report"
    return await execute_agent(req, db)


@router.post("/agent/analyze")
async def analyze_data(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    """Shortcut to run data analysis."""
    req.agent_type = "data_table"
    return await execute_agent(req, db)
