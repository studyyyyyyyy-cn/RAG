"""Multi-source LLM manager using litellm for unified API access."""
import logging
from typing import AsyncGenerator

import litellm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.config import decrypt_api_key

logger = logging.getLogger(__name__)

# litellm configuration
litellm.drop_params = True  # Silently drop unsupported params per provider


# Provider-to-litellm prefix mapping
PROVIDER_PREFIX = {
    "openai": "",
    "anthropic": "anthropic/",
    "deepseek": "openai/",
    "ollama": "ollama/",
    "zhipu": "openai/",          # zhipu uses OpenAI-compatible API
    "qwen": "openai/",           # qwen uses OpenAI-compatible API
    "vllm": "openai/",           # vllm uses OpenAI-compatible API
    "proxy_openai": "openai/",   # proxy service with OpenAI format
    "proxy_custom": "openai/",   # proxy service with custom format
    "proxy_anthropic": "openai/", # Anthropic proxy service (OpenAI-compatible)
}


async def get_llm_config(db: AsyncSession, config_id: str = None) -> LLMConfig | None:
    """Get LLM config by ID, or the default config."""
    if config_id:
        return await db.get(LLMConfig, config_id)

    result = await db.execute(
        select(LLMConfig).where(LLMConfig.is_default == True, LLMConfig.is_active == True)
    )
    return result.scalars().first()


def _build_litellm_model(config: LLMConfig) -> str:
    """Build the litellm model string from config."""
    model_name = (config.model_name or "").strip()

    # If the saved model name already includes a provider prefix, keep it as-is.
    # This avoids generating invalid values like "openai/openai/gpt-4o".
    if "/" in model_name:
        return model_name

    prefix = PROVIDER_PREFIX.get(config.provider, "openai/")
    return f"{prefix}{model_name}"


async def chat_completion(
    messages: list[dict],
    config: LLMConfig,
    stream: bool = True,
    **kwargs,
) -> AsyncGenerator[str, None] | str:
    """Call LLM with unified interface.

    If stream=True, yields text chunks as an async generator.
    If stream=False, returns the full response text.
    """
    model = _build_litellm_model(config)
    params = config.params or {}

    # Decrypt API key
    api_key = decrypt_api_key(config.api_key_encrypted)

    call_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": params.get("temperature", 0.1),
        "max_tokens": params.get("max_tokens", 4096),
        "stream": stream,
    }

    if api_key:
        call_kwargs["api_key"] = api_key
    if config.base_url:
        call_kwargs["api_base"] = config.base_url

    # For proxy services, ensure proper handling
    if config.provider in ("proxy_openai", "proxy_custom", "proxy_anthropic"):
        # Proxy services typically use OpenAI-compatible format
        # Ensure the model name doesn't have duplicate prefix
        if model.startswith("openai/"):
            call_kwargs["model"] = model.replace("openai/", "", 1)
        # Some proxy services require explicit api_base
        if not config.base_url:
            raise ValueError("Base URL is required for proxy services")

    if stream:
        return _stream_response(**call_kwargs)
    else:
        response = await litellm.acompletion(**call_kwargs)
        return response.choices[0].message.content


async def _stream_response(**kwargs) -> AsyncGenerator[str, None]:
    """Stream LLM response chunks."""
    response = await litellm.acompletion(**kwargs)
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


async def test_connection(config: LLMConfig) -> dict:
    """Test LLM connection with a simple request."""
    try:
        result = await chat_completion(
            messages=[{"role": "user", "content": "Hello, respond with 'OK'."}],
            config=config,
            stream=False,
        )
        return {"status": "ok", "response": result}
    except Exception as e:
        import traceback
        from app.config import settings as app_settings
        error_detail = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"LLM test connection failed: {error_detail}\n{error_trace}")
        result = {"status": "error", "detail": error_detail}
        # Only include traceback in debug mode
        if app_settings.DEBUG:
            result["trace"] = error_trace
        return result
