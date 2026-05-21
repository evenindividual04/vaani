"""Runtime config API — LLM provider toggle and mock mode signal."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_scope

router = APIRouter(prefix="/config", tags=["config"])

LLMProvider = Literal["auto", "groq", "gemini"]

# Module-level override; resets on process restart (intentional for dev/demo)
_llm_provider: LLMProvider = "auto"


def get_llm_provider_override() -> LLMProvider:
    return _llm_provider


class ProviderRequest(BaseModel):
    provider: LLMProvider


@router.get("")
async def get_config(user: dict = Depends(require_scope("read"))):
    return {"llm_provider": _llm_provider}


@router.put("/llm_provider")
async def set_llm_provider(
    body: ProviderRequest,
    user: dict = Depends(require_scope("write")),
):
    global _llm_provider
    _llm_provider = body.provider
    return {"llm_provider": _llm_provider}
