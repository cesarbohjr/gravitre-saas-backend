"""Browser extension API — front door onto catalog + Module A (v1 overlay)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import require_org_member
from app.config import Settings, get_settings
from app.services.extension_bridge_service import (
    EXTENSION_ALLOWED_ACTIONS,
    connected_integrations,
    enrich_from_page_context,
    execute_extension_action,
)
from app.services.tool_types import ToolContext

router = APIRouter(prefix="/api/extension", tags=["extension"])


class PageContextBody(BaseModel):
    pageUrl: str | None = None
    pageContext: dict[str, Any] = Field(default_factory=dict)
    environment: str = "production"


class ExtensionActionBody(BaseModel):
    """Propose a write (invokeAction+params) or confirm with server-issued token.

    ``confirmed`` is accepted for backward compatibility but ignored — only
    ``confirmationToken`` from a prior needs_confirmation response authorizes writes.
    """

    invokeAction: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    pageUrl: str | None = None
    confirmationToken: str | None = None
    confirmed: bool = False  # ignored — never trusted
    environment: str = "production"


def _tool_context(
    *,
    settings: Settings,
    org_id: str,
    user_id: str,
    environment: str,
) -> ToolContext:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=user_id,
        environment_name=environment or "production",
    )


@router.get("/session")
async def extension_session(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id, role = member
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connected = connected_integrations(client, str(org_id))
    return {
        "userId": str(user["user_id"]),
        "orgId": str(org_id),
        "role": role,
        "connectedIntegrations": connected,
        "allowedActions": sorted(EXTENSION_ALLOWED_ACTIONS),
        "model": "overlay_and_approve",
        "openAppUrl": "https://gravitre.app",
    }


@router.post("/enrich")
async def extension_enrich(
    body: PageContextBody,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id, _role = member
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org required")
    user_id = str(user["user_id"])
    ctx = _tool_context(
        settings=settings,
        org_id=str(org_id),
        user_id=user_id,
        environment=body.environment,
    )
    connected = connected_integrations(ctx.client, str(org_id), body.environment)
    if not connected:
        return {
            "surface": "unknown",
            "matches": [],
            "suggestions": [],
            "connectedIntegrations": [],
            "voiceNote": "Connect Apollo or HubSpot in Gravitree to enrich this page.",
            "openInGravitreeUrl": "/connectors",
        }
    return enrich_from_page_context(
        ctx,
        page_url=body.pageUrl,
        page_context=body.pageContext or {},
        connected=connected,
    )


@router.post("/actions/execute")
async def extension_execute_action(
    body: ExtensionActionBody,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id, _role = member
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org required")
    user_id = str(user["user_id"])
    ctx = _tool_context(
        settings=settings,
        org_id=str(org_id),
        user_id=user_id,
        environment=body.environment,
    )
    try:
        return execute_extension_action(
            ctx,
            org_id=str(org_id),
            user_id=user_id,
            action=body.invokeAction,
            params=body.params or {},
            page_url=body.pageUrl,
            confirmation_token=body.confirmationToken,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
