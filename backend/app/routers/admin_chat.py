"""Admin chat intelligence settings and conversation health metrics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool, StrictInt

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.chat_dialogue_settings import (
    DEFAULT_DIALOGUE_SETTINGS,
    load_chat_dialogue_settings,
    save_chat_dialogue_settings,
)
from app.services.persona_service import get_persona_service
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/admin/chat", tags=["chat-admin"])


class PersonaDefaultUpdate(BaseModel):
    persona_key: str = Field(min_length=1)


class DialogueSettingsUpdate(BaseModel):
    clarification_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    escalation_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    proactive_suggestions_enabled: bool | None = None
    max_suggestions_per_response: int | None = Field(default=None, ge=0, le=5)
    consensus_enabled: bool | None = None
    sentiment_detection_enabled: bool | None = None
    memory_retention_days: int | None = Field(default=None, ge=1, le=365)
    evaluation_feedback_enabled: StrictBool | None = None
    evaluation_feedback_retention_days: StrictInt | None = Field(default=None, ge=1, le=90)


@router.get("/personas")
async def list_chat_personas(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    dialogue = await load_chat_dialogue_settings(org_id, settings)
    org_default = str(dialogue.get("default_persona") or "friendly_assistant")
    return {
        "personas": get_persona_service(settings).list_personas(org_default),
        "org_default_persona": org_default,
    }


@router.post("/personas/default")
async def set_default_chat_persona(
    body: PersonaDefaultUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    persona_service = get_persona_service(settings)
    if body.persona_key not in persona_service.COMMUNICATION_PERSONAS:
        return {"status": "error", "message": "Unknown persona_key"}
    await save_chat_dialogue_settings(
        org_id,
        {"default_persona": body.persona_key},
        settings,
    )
    return {"status": "ok", "default_persona": body.persona_key}


@router.get("/dialogue-settings")
async def get_dialogue_settings(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    loaded = await load_chat_dialogue_settings(org_id, settings)
    return {key: loaded.get(key, DEFAULT_DIALOGUE_SETTINGS[key]) for key in DEFAULT_DIALOGUE_SETTINGS}


@router.post("/dialogue-settings")
async def update_dialogue_settings(
    body: DialogueSettingsUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    saved = await save_chat_dialogue_settings(org_id, updates, settings)
    return {key: saved.get(key, DEFAULT_DIALOGUE_SETTINGS[key]) for key in DEFAULT_DIALOGUE_SETTINGS}


LOW_QUALITY_THRESHOLD = 0.5


@router.get("/conversation-health")
async def get_conversation_health(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows: list[dict[str, Any]] = []
    try:
        rows = (
            client.table("user_query_patterns")
            .select("response_quality, query_category, created_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []

    total = max(len(rows), 1)
    qualities = [float(r["response_quality"]) for r in rows if r.get("response_quality") is not None]
    clarify_rate = sum(1 for r in rows if r.get("query_category") == "help") / total
    # Module C / STA-331: never invent a 0.65 "live" confidence when there is no data.
    has_quality = bool(qualities)
    avg_confidence = (sum(qualities) / len(qualities)) if has_quality else None

    # Honest metrics only. Frustration, escalation and consensus-trigger rates
    # used to be arithmetic over response_quality / the "help" category share
    # ((1 - quality) * 0.5, 0.4 - quality, clarify * 0.3) presented as if they
    # were measured. Nothing records those signals, so they are not reported;
    # low_quality_rate_7d is the measured share of rated responses below
    # LOW_QUALITY_THRESHOLD.
    low_quality_rate = (
        sum(1 for q in qualities if q < LOW_QUALITY_THRESHOLD) / len(qualities) if has_quality else None
    )
    return {
        "low_quality_rate_7d": round(low_quality_rate, 3) if low_quality_rate is not None else None,
        "low_quality_threshold": LOW_QUALITY_THRESHOLD,
        "avg_clarification_rate_7d": round(clarify_rate, 3),
        "clarification_rate_source": "query_category == 'help' share",
        "avg_confidence_7d": round(avg_confidence, 3) if avg_confidence is not None else None,
        "confidence_is_estimate": False,
        "confidence_source": "response_quality" if has_quality else "insufficient_data",
        "not_measured": ["frustration", "escalation_rate", "consensus_trigger_rate"],
        "sample_size": len(rows),
        "quality_sample_size": len(qualities),
    }


@router.get("/evaluation-feedback")
async def get_evaluation_feedback(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Metrics-only review input; never an automatic prompt training endpoint."""
    loaded = await load_chat_dialogue_settings(org_id, settings)
    if loaded.get("evaluation_feedback_enabled") is not True:
        return {"status": "disabled", "automatic_promotion": False}
    from app.core.io_pool import run_io
    from app.services.dialogue_evaluation_feedback import feedback_summary

    try:
        client = get_supabase_client(settings)
        summary = await run_io(lambda: feedback_summary(
            client, org_id, retention_days=loaded.get("evaluation_feedback_retention_days", 30),
        ))
    except Exception:
        return {"status": "unavailable", "automatic_promotion": False}
    return {"status": "available", **summary}
