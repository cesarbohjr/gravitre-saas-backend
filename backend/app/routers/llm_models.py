"""Read-only LLM catalog for model pickers (assistant, agents, ML registry)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.services.llm_catalog import configured_llm_providers, visible_llm_models

router = APIRouter(prefix="/api/models", tags=["llm-models"])


@router.get("/llm-catalog")
async def get_llm_catalog(
    _user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Current (non-deprecated) LLMs whose provider has an API key configured.

    Deprecated ids are omitted here but remain routable for saved agents.
    """
    providers = configured_llm_providers(settings)
    return {
        "providers": sorted(providers),
        "models": [m.to_public_dict() for m in visible_llm_models(providers)],
    }
