"""Phase 3: read and correct customer observations for one business entity.

Reads are open to org members; corrections and retractions need an admin and
are audited. Off (404) unless ENTITY_OBSERVATIONS_ENABLED is true.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.services.entity_observations import (
    DIMENSIONS,
    TABLE,
    apply_correction,
    observations_enabled,
    trend,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/entities", tags=["entity-observations"])


class CorrectionRequest(BaseModel):
    label: str | None = None
    retract: bool = False
    note: str = Field(default="", max_length=500)


def _require_enabled(settings: Settings) -> None:
    if not observations_enabled(settings):
        raise HTTPException(status_code=404, detail="Not found")


def _entity_row(client: Any, org_id: str, entity_id: str) -> dict[str, Any]:
    res = (
        client.table("org_business_entities")
        .select("id, display_name, kind")
        .eq("org_id", org_id)
        .eq("id", entity_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Entity not found")
    return res.data[0]


@router.get("/{entity_id}/observations")
def list_entity_observations(
    entity_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _require_enabled(settings)
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = shared_service_client(settings, create_client)
    entity = _entity_row(client, org_id, entity_id)
    rows = (
        client.table(TABLE)
        .select(
            "id, dimension, label, score, confidence, evidence_quote, source_system, source_record_type,"
            " source_record_id, observed_at, extractor_version, status, correction"
        )
        .eq("org_id", org_id)
        .eq("entity_id", entity_id)
        .order("observed_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )
    signals = (
        client.table("entity_behavior_signals")
        .select("signal, value, baseline, window_end, rule_version, evidence_count")
        .eq("org_id", org_id)
        .eq("entity_id", entity_id)
        .order("window_end", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    return {
        "entity": entity,
        "observations": rows,
        "trends": [trend(rows, dimension=d) for d in DIMENSIONS],
        "behaviorSignals": signals,
    }


@router.post("/{entity_id}/observations/{observation_id}/correction")
def correct_entity_observation(
    entity_id: str,
    observation_id: str,
    body: CorrectionRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _require_enabled(settings)
    user, org_id = admin_ctx
    client = shared_service_client(settings, create_client)
    _entity_row(client, org_id, entity_id)
    try:
        out = apply_correction(
            client,
            org_id=org_id,
            observation_id=observation_id,
            actor_id=str(user["user_id"]),
            label=body.label,
            retract=body.retract,
            note=body.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Observation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action="entity_observation.retracted" if body.retract else "entity_observation.corrected",
        resource_type="entity_observation",
        resource_id=observation_id,
        metadata={"entity_id": entity_id, "previous": out.get("previous"), "correction": out.get("correction")},
    )
    return out
