"""Tenant-scoped Intelligence Overview contract (advisory only).

This API deliberately does not claim a connector-wide historical sweep is complete
until a separately certified orchestration worker writes verified results.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.services.intelligence_router import CAPABILITY_NAMES
from app.services.recommendation_heuristics_service import (
    build_heuristic_recommendations,
    load_connected_connectors,
    load_usage_by_connector,
)
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/intelligence/overview", tags=["intelligence-overview"])
Mode = Literal["conservative", "balanced", "proactive"]
CAPABILITIES = frozenset(CAPABILITY_NAMES)
DESCRIPTIONS = {
    "contextual": "Understands the business context behind a question.",
    "sentiment": "Looks for changes in customer tone and friction.",
    "causal": "Investigates potential causes without confusing correlation with proof.",
    "temporal": "Recognizes changes over time and timing patterns.",
    "relational": "Connects relevant people, accounts and business entities.",
    "adaptive": "Suggests improvements based on observed outcomes.",
    "predictive": "Estimates future risks and opportunities when enough evidence exists.",
}


class CapabilitySetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode = "balanced"


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: dict[str, CapabilitySetting] = Field(min_length=1, max_length=7)


def _actor(member: tuple) -> str:
    user = member[0]
    return str(user.get("user_id") or user.get("sub") or user.get("id") or "")


def _db(settings: Settings):
    return get_supabase_client(settings)


def _profile(client, org_id: str) -> dict:
    result = client.table("intelligence_overview_profiles").select("capabilities,updated_at").eq("org_id", org_id).limit(1).execute()
    return (result.data or [{}])[0]


def _settings(raw: dict) -> dict:
    return {
        name: {
            "mode": (raw.get(name) or {}).get("mode", "balanced")
            if isinstance(raw.get(name), dict) and (raw.get(name) or {}).get("mode") in ("balanced", "conservative", "proactive")
            else "balanced",
            "description": DESCRIPTIONS[name],
            "behavior_wired": name == "adaptive",  # Other capabilities are not yet policy wired.
        }
        for name in CAPABILITY_NAMES
    }


@router.get("")
def overview(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict:
    client = _db(settings)
    profile = _profile(client, org_id)
    connections = load_connected_connectors(client, org_id)
    usable = [c for c in connections if c.get("executable")]
    vendors = sorted({c["vendor"] for c in usable})
    count = len(vendors)
    readiness = "limited" if count == 1 else "cross_system_candidate" if count >= 2 else "insufficient"
    # Count alone never certifies actual historical depth, departmental coverage or data quality.
    usage = load_usage_by_connector(client, org_id)
    cards = build_heuristic_recommendations(connected_connectors=connections, usage_by_connector=usage)
    latest = (
        client.table("intelligence_overview_sweeps")
        .select("id,status,created_at,started_at,completed_at,error_code,results")
        .eq("org_id", org_id).order("created_at", desc=True).limit(1).execute()
    )
    return {
        "schema_version": "intelligence_overview_v1",
        "org_id": org_id,
        "capabilities": _settings(profile.get("capabilities") or {}),
        "knowledge": {"usable_connectors": count, "vendors": vendors, "facts": None, "freshness": None},
        "readiness": {"tier": readiness, "connector_count": count, "coverage_verified": False,
                      "comprehensive": False, "recommended_connector_count": 3},
        "insights": [],
        "recommendations": cards.get("recommendations") or [],
        "actions": [],
        "outcomes": [],
        "latest_sweep": (latest.data or [None])[0],
        "advisory_only": True,
        "data_limitations": ["Cross-connector historical analysis has not been certified.",
                             "No business-wide health score is inferred from connector count."],
    }


@router.patch("/profile")
def update_profile(
    body: ProfilePatch,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict:
    unknown = set(body.capabilities) - CAPABILITIES
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown capabilities: {', '.join(sorted(unknown))}")
    client = _db(settings)
    previous = _profile(client, org_id).get("capabilities") or {}
    merged = {**previous, **{k: v.model_dump() for k, v in body.capabilities.items()}}
    actor = _actor(admin)
    result = client.table("intelligence_overview_profiles").upsert(
        {"org_id": org_id, "capabilities": merged, "updated_at": datetime.now(timezone.utc).isoformat()},
        on_conflict="org_id",
    ).execute()
    write_audit_event(client, org_id, actor, "intelligence.overview.profile_updated", "intelligence_overview_profile",
                      org_id, metadata={"previous": previous, "current": merged, "router_policy_applied": "adaptive" in body.capabilities})
    return {"capabilities": _settings(merged), "saved": bool(result.data),
            "router_policy_applied": "adaptive" in body.capabilities, "advisory_only": True}


@router.post("/sweeps", status_code=202)
def request_sweep(
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict:
    # Queue the intent durably. No ingestion is started or implied: worker activation
    # requires an audited connector permission + orchestration implementation.
    client = _db(settings)
    connections = load_connected_connectors(client, org_id)
    vendors = sorted({c["vendor"] for c in connections if c.get("executable")})
    if not vendors:
        raise HTTPException(status_code=409, detail="Connect at least one usable data source first.")
    existing = (client.table("intelligence_overview_sweeps").select("id,status")
                .eq("org_id", org_id).in_("status", ["queued", "running"]).limit(1).execute())
    if existing.data:
        return {"sweep": existing.data[0], "started": False, "orchestrator_enabled": False}
    result = client.table("intelligence_overview_sweeps").insert({
        "org_id": org_id, "requested_by": _actor(admin) or None,
        "scope": {"vendors_requested": vendors, "connector_count": len(vendors)},
        "status": "queued",
    }).execute()
    sweep = (result.data or [None])[0]
    if not sweep:
        raise HTTPException(status_code=503, detail="Could not persist sweep request")
    write_audit_event(client, org_id, _actor(admin), "intelligence.overview.sweep_requested",
                      "intelligence_overview_sweep", str(sweep["id"]),
                      metadata={"vendors_requested": vendors, "execution_started": False})
    return {"sweep": sweep, "started": False, "orchestrator_enabled": False,
            "message": "Request saved; full connector analysis awaits certified orchestration."}


@router.get("/sweeps/{sweep_id}")
def sweep_status(
    sweep_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict:
    result = (_db(settings).table("intelligence_overview_sweeps")
              .select("id,status,scope,results,error_code,created_at,started_at,completed_at")
              .eq("org_id", org_id).eq("id", sweep_id).limit(1).execute())
    if not result.data:
        raise HTTPException(status_code=404, detail="Sweep not found")
    return {"sweep": result.data[0], "orchestrator_enabled": False}
