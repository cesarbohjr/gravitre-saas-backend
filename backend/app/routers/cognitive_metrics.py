"""Admin API for org metric definitions (CognitiveTurnKernel Phase 5)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services import cognitive_metrics as metrics_svc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/cognitive-metrics", tags=["cognitive-metrics-admin"])


def _client(settings: Settings) -> Any:
    from app.workflows.repository import get_supabase_client

    return get_supabase_client(settings)


class MetricUpsertBody(BaseModel):
    label: str | None = None
    formula: str | None = None
    source_system: str | None = None
    owner: str | None = None
    agent_id: str | None = Field(
        default=None,
        description="Optional agent id for resolve context; not stored on the definition row.",
    )


@router.get("")
async def list_cognitive_metrics(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List org-scoped metric definitions."""
    try:
        client = _client(settings)
        rows = metrics_svc.list_metric_definitions(client, org_id, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_list_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="org_metric_definitions unavailable",
        ) from exc
    return {"definitions": rows, "orgId": org_id, "limit": limit}


@router.put("/{metric_key}")
async def upsert_cognitive_metric(
    metric_key: str,
    body: MetricUpsertBody,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Insert or update an org metric definition."""
    key = (metric_key or "").strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metric_key required")
    try:
        client = _client(settings)
        row = metrics_svc.upsert_metric_definition(
            client,
            org_id,
            key,
            label=body.label,
            formula=body.formula,
            source_system=body.source_system,
            owner=body.owner,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_upsert_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="org_metric_definitions unavailable",
        ) from exc
    if not row:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="metric upsert failed",
        )
    return {"definition": row, "orgId": org_id}


@router.get("/{metric_key}/resolve")
async def resolve_cognitive_metric(
    metric_key: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    agent_id: str | None = Query(default=None),
    fallback_label: str | None = Query(default=None),
) -> dict[str, Any]:
    """Resolve a metric for agent use via cognitive_metrics.resolve_metric_for_agent."""
    key = (metric_key or "").strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="metric_key required")
    try:
        client = _client(settings)
        resolved = metrics_svc.resolve_metric_for_agent(
            client,
            org_id,
            key,
            agent_id=agent_id,
            fallback_label=fallback_label,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_resolve_failed error=%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="metric resolve unavailable",
        ) from exc
    return {"resolved": resolved, "orgId": org_id}
