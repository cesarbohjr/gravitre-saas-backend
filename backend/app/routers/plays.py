"""Read-only Play catalog/readiness API.

Execution remains in canonical workflows. This router does not execute Plays
or mutate connector/workflow/governance state.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_environment_context, require_org_member
from app.capabilities.registry import connected_vendors
from app.config import Settings, get_settings
from app.plays.catalog import PLATFORM_PLAY_TEMPLATES, get_platform_play
from app.plays.outcomes import list_play_business_results
from app.plays.readiness import resolve_play_readiness
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/plays", tags=["plays"])


def _member_org(member: tuple[dict, str, str]) -> str:
    _user, org_id, _role = member
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    return org_id


def _template_payload(play: Any) -> dict[str, Any]:
    payload = play.as_dict()
    payload["executable"] = False
    payload["executionAuthority"] = "canonical_workflow_runtime"
    return payload


@router.get("")
async def list_plays(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    connected = connected_vendors(client, org_id, environment_name)
    items = []
    for play in PLATFORM_PLAY_TEMPLATES:
        readiness = resolve_play_readiness(
            play,
            connected_vendors=connected,
            client=client,
            org_id=org_id,
            policy_authorized_actions=set(),
        )
        items.append(
            {
                "play": _template_payload(play),
                "readiness": readiness.as_dict(),
            }
        )
    return {
        "plays": items,
        "count": len(items),
        "executionAuthority": "canonical_workflow_runtime",
        "policyNote": (
            "ACT WITHIN POLICY is not inferred by this read endpoint. "
            "It requires an effective runtime policy evaluation for a specific agent/action/context."
        ),
    }


@router.get("/{play_key}/readiness")
async def get_play_readiness(
    play_key: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    play = get_platform_play(play_key)
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    connected = connected_vendors(client, org_id, environment_name)
    readiness = resolve_play_readiness(
        play,
        connected_vendors=connected,
        client=client,
        org_id=org_id,
        policy_authorized_actions=set(),
    )
    return {
        "play": _template_payload(play),
        "readiness": readiness.as_dict(),
        "executionAuthority": "canonical_workflow_runtime",
    }


@router.get("/{play_key}/outcomes")
async def get_play_outcomes(
    play_key: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    play = get_platform_play(play_key)
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    rows = list_play_business_results(client, org_id, play_key=play.key, limit=limit)
    return {
        "playKey": play.key,
        "outcomes": rows,
        "count": len(rows),
        "truthRule": "Execution success is not business success; verified business results require source-of-record evidence.",
    }
