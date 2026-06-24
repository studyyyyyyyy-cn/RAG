"""LLM provider configuration API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.llm_config import LLMConfig
from app.core.llm_manager import test_connection
from app.config import encrypt_api_key

router = APIRouter()


class LLMConfigCreate(BaseModel):
    provider: str           # openai / anthropic / deepseek / ollama / zhipu / qwen / vllm
    model_name: str         # gpt-4o, claude-sonnet-4-20250514, deepseek-chat, etc.
    display_name: str       # User-friendly name
    api_key: str | None = None
    base_url: str | None = None
    is_default: bool = False
    params: dict | None = None  # temperature, max_tokens, etc.


class LLMConfigUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    params: dict | None = None


@router.post("/llm/configs")
async def create_llm_config(
    data: LLMConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a new LLM provider configuration."""
    # If setting as default, unset current default
    if data.is_default:
        result = await db.execute(select(LLMConfig).where(LLMConfig.is_default == True))
        for existing in result.scalars():
            existing.is_default = False

    config = LLMConfig(
        provider=data.provider,
        model_name=data.model_name,
        display_name=data.display_name,
        api_key_encrypted=encrypt_api_key(data.api_key) if data.api_key else None,
        base_url=data.base_url,
        is_default=data.is_default,
        params=data.params or {"temperature": 0.1, "max_tokens": 4096},
    )
    db.add(config)
    await db.flush()

    return {
        "id": str(config.id),
        "provider": config.provider,
        "model_name": config.model_name,
        "display_name": config.display_name,
        "is_default": config.is_default,
    }


@router.get("/llm/configs")
async def list_llm_configs(
    db: AsyncSession = Depends(get_db),
):
    """List all LLM configurations."""
    result = await db.execute(select(LLMConfig).order_by(LLMConfig.created_at.desc()))
    configs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "provider": c.provider,
                "model_name": c.model_name,
                "display_name": c.display_name,
                "base_url": c.base_url,
                "is_default": c.is_default,
                "is_active": c.is_active,
                "params": c.params,
                "has_api_key": bool(c.api_key_encrypted),
            }
            for c in configs
        ],
    }


@router.put("/llm/configs/{config_id}")
async def update_llm_config(
    config_id: str,
    data: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an LLM configuration."""
    config = await db.get(LLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")

    # If setting as default, unset current default
    if data.is_default:
        result = await db.execute(select(LLMConfig).where(LLMConfig.is_default == True))
        for existing in result.scalars():
            existing.is_default = False

    update_data = data.model_dump(exclude_unset=True)
    if "api_key" in update_data:
        raw_key = update_data.pop("api_key")
        config.api_key_encrypted = encrypt_api_key(raw_key) if raw_key else None
    for key, value in update_data.items():
        setattr(config, key, value)

    return {"detail": "Updated", "id": str(config.id)}


@router.delete("/llm/configs/{config_id}")
async def delete_llm_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an LLM configuration."""
    config = await db.get(LLMConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="LLM config not found")

    await db.delete(config)
    return {"detail": "Deleted"}


@router.post("/llm/configs/test")
async def test_llm_config(
    data: LLMConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """Test LLM connectivity without saving."""
    temp_config = LLMConfig(
        provider=data.provider,
        model_name=data.model_name,
        display_name=data.display_name,
        api_key_encrypted=encrypt_api_key(data.api_key) if data.api_key else None,
        base_url=data.base_url,
        params=data.params or {"temperature": 0.1, "max_tokens": 100},
    )
    result = await test_connection(temp_config)
    return result
