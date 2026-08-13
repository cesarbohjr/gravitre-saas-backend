"""Admin API for CognitiveTurnKernel traces (org-scoped)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/cognitive-turns", tags=["cognitive-turns-admin"])


def _client(settings: Settings) -> Any:
    from app.workflows.repository import get_supabase_client

    return get_supabase_client(settings)


@router.get("")
async def list_cognitive_turn_traces(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List recent cognitive turn traces for the org."""
    try:
        client = _client(settings)
        rows = (
            client.table("cognitive_turn_traces")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_turn_list_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cognitive_turn_traces unavailable",
        ) from exc

    return {"traces": rows, "orgId": org_id, "limit": limit, "offset": offset}


@router.get("/{turn_id}")
async def get_cognitive_turn_trace(
    turn_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return a single cognitive turn trace (org-scoped)."""
    try:
        client = _client(settings)
        rows = (
            client.table("cognitive_turn_traces")
            .select("*")
            .eq("org_id", org_id)
            .eq("turn_id", turn_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_turn_get_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cognitive_turn_traces unavailable",
        ) from exc

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    return {"trace": rows[0], "orgId": org_id}
