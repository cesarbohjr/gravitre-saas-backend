"""Intelligence: revenue opportunities from the CRM, and sharing a finding with the team."""
from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import require_org_member
from app.config import Settings, get_settings
from app.services.intelligence_share_service import (
    ShareDeliveryError,
    ShareInputError,
    share_finding,
    share_options,
)
from app.services.revenue_opportunities_service import get_revenue_opportunities
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/intelligence", tags=["intelligence-findings"])


class ShareRequest(BaseModel):
    app: str = Field(..., min_length=1, max_length=16)
    channelId: str | None = Field(default=None, max_length=32)
    personId: str | None = Field(default=None, max_length=64)
    title: str = Field(..., min_length=1, max_length=400)
    summary: str = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=2000)
    path: str | None = Field(default=None, max_length=400)
    findingId: str | None = Field(default=None, max_length=200)


def _user_id(user: dict[str, Any]) -> str:
    return str(user.get("user_id") or user.get("sub") or "")


def _display_name(client: Any, user: dict[str, Any]) -> str:
    uid = _user_id(user)
    try:
        rows = client.table("users").select("full_name, email").eq("auth_user_id", uid).limit(1).execute().data or []
    except Exception:  # noqa: BLE001
        rows = []
    row = rows[0] if rows else {}
    name = str(row.get("full_name") or "").strip()
    email = str(row.get("email") or user.get("email") or "").strip()
    return name or (email.split("@")[0] if email else "a teammate")


@router.get("/revenue-opportunities")
async def revenue_opportunities(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return await asyncio.to_thread(get_revenue_opportunities, client, org_id, settings, refresh=refresh)


@router.get("/share/options")
async def share_options_route(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, org_id, _role = member
    client = get_supabase_client(settings)
    return await asyncio.to_thread(share_options, client, org_id, settings, user_id=_user_id(user))


@router.post("/share")
async def share_route(
    body: ShareRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, org_id, _role = member
    client = get_supabase_client(settings)
    sender = await asyncio.to_thread(_display_name, client, user)
    try:
        return await asyncio.to_thread(
            share_finding,
            client,
            org_id,
            settings,
            user_id=_user_id(user),
            sender_name=sender,
            app=body.app,
            channel_id=body.channelId,
            person_id=body.personId,
            title=body.title,
            summary=body.summary,
            note=body.note,
            path=body.path,
            finding_id=body.findingId,
        )
    except ShareInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ShareDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
