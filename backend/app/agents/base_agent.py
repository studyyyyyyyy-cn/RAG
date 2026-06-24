"""Base agent class and intent router for multi-format output."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.llm_manager import chat_completion
from app.models.llm_config import LLMConfig
from app.utils.prompt_templates import INTENT_DETECTION_PROMPT

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for output agents."""

    agent_type: str = "base"

    @abstractmethod
    async def execute(self, query: str, context: list[dict], llm_config: LLMConfig) -> dict:
        """Execute the agent and return structured output.

        Returns dict compatible with the unified output protocol.
        """
        ...


async def detect_intent(query: str, llm_config: LLMConfig) -> str:
    """Use LLM to detect the best output format for a query.

    Returns: text | chart | report | webpage | data_table
    """
    prompt = INTENT_DETECTION_PROMPT.format(query=query)
    messages = [{"role": "user", "content": prompt}]

    try:
        result = await chat_completion(messages, llm_config, stream=False)
        intent = result.strip().lower()
        if intent in ("text", "chart", "report", "webpage", "data_table"):
            return intent
    except Exception as e:
        logger.warning(f"Intent detection failed: {e}")

    return "text"  # Default fallback
