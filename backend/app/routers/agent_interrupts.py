"""STA-108: Human-in-the-loop interrupt API (pause/cancel running agent work)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.agent_interrupt_service import request_interrupt

router = APIRouter(prefix="/api/agent-interrupts", tags=["agent-interrupts"])


class InterruptRequest(BaseModel):
    target_type: Literal["agent_job", "workflow_run", "operator_session"] = Field(alias="targetType")
    target_id: str = Field(alias="targetId")
    signal: Literal["pause", "cancel"] = "cancel"

    model_config = {"populate_by_name": True}


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "targetType": row.get("target_type"),
        "targetId": str(row.get("target_id")),
        "signal": row.get("signal"),
        "status": row.get("status"),
        "source": row.get("source"),
        "createdAt": row.get("created_at"),
        "appliedEagerly": bool(row.get("applied_eagerly")),
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_interrupt(
    body: InterruptRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        row = request_interrupt(
            client,
            org_id=org_id,
            target_type=body.target_type,
            target_id=body.target_id,
            signal=body.signal,
            actor_id=current_user.get("user_id"),
            source="ui",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"interrupt": _public(row)}
