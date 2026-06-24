"""MCP Tools definitions for RAG capabilities."""

import logging
from typing import Any

from app.core.retriever import retrieve, RetrievalResponse
from app.core.generator import generate_answer
from app.models.database import async_session
from app.models.knowledge_base import KnowledgeBase
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def list_knowledge_bases() -> dict:
    """List all available knowledge bases.

    Returns:
        dict: List of knowledge bases with id, name, description
    """
    async with async_session() as db:
        result = await db.execute(select(KnowledgeBase))
        kbs = result.scalars().all()

        return {
            "knowledge_bases": [
                {
                    "id": str(kb.id),
                    "name": kb.name,
                    "description": kb.description or "",
                }
                for kb in kbs
            ]
        }


async def rag_chat(
    query: str,
    kb_id: str,
    history: list[dict] | None = None,
    top_k: int = 5,
    enable_agent: bool = True,
) -> dict:
    """RAG chat: retrieve relevant documents and generate answer.

    Args:
        query: User question
        kb_id: Knowledge base ID
        history: Conversation history (optional)
        top_k: Number of retrieval chunks (default 5)
        enable_agent: Enable intelligent agent routing (default True)

    Returns:
        dict: Answer with references and confidence
    """
    async with async_session() as db:
        # Verify knowledge base exists
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb:
            return {
                "error": f"Knowledge base not found: {kb_id}",
                "answer": None,
                "references": [],
            }

        # Generate answer using RAG pipeline with agent routing
        answer = await generate_answer(
            query=query,
            kb_id=kb_id,
            db=db,
            conversation_history=history or [],
            stream=False,
            enable_agent=enable_agent,
        )

        # Extract content and citations
        content = answer.get("content", {})
        text = content.get("text", "")
        citations = content.get("citations", [])
        metadata = answer.get("metadata", {})
        confidence = answer.get("confidence", 0.0)
        answer_type = answer.get("type", "text")

        result = {
            "answer": text,
            "type": answer_type,
            "references": [
                {
                    "source": c.get("source", "Unknown"),
                    "page": c.get("page_number"),
                    "content": c.get("content", "")[:200] + "..." if len(c.get("content", "")) > 200 else c.get("content", ""),
                }
                for c in citations
            ],
            "confidence": confidence,
            "model_used": metadata.get("model_used"),
            "agent_type": metadata.get("agent_type", "text"),
        }
        
        # Add extra content for non-text types
        if answer_type == "chart":
            result["chart_spec"] = content.get("chart_spec")
        elif answer_type == "report":
            result["html_content"] = content.get("html_content")
        elif answer_type == "webpage":
            result["html_content"] = content.get("html_content")
        elif answer_type == "composite":
            result["data_table"] = content.get("data_table")
            result["chart_spec"] = content.get("chart_spec")
            result["insights"] = content.get("insights", [])
        
        return result


# Tool definitions for MCP protocol
TOOL_DEFINITIONS = [
    {
        "name": "list_knowledge_bases",
        "description": "List all available knowledge bases. Use this to get the list of knowledge bases and their IDs before querying.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "rag_chat",
        "description": "Ask a question and get an answer based on the knowledge base. This performs RAG (Retrieval-Augmented Generation) with intelligent agent routing - automatically detects if the question needs chart, report, or other specialized output formats.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question to ask",
                },
                "kb_id": {
                    "type": "string",
                    "description": "Knowledge base ID (use list_knowledge_bases to get available IDs)",
                },
                "history": {
                    "type": "array",
                    "description": "Previous conversation history (optional)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of documents to retrieve (default 5)",
                    "default": 5,
                },
                "enable_agent": {
                    "type": "boolean",
                    "description": "Enable intelligent agent routing - auto-detect output format (default true)",
                    "default": True,
                },
            },
            "required": ["query", "kb_id"],
        },
    },
]


# Tool handler mapping
TOOL_HANDLERS = {
    "list_knowledge_bases": list_knowledge_bases,
    "rag_chat": rag_chat,
}
