"""Tenant-scoped Intelligence Overview contract (advisory only).

This API deliberately does not claim a connector-wide historical sweep is complete
until a separately certified orchestration worker writes verified results.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import get_org_context, get_environment_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.services.intelligence_router import CAPABILITY_NAMES
from app.services.intelligence_overview_readiness import score_readiness
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
            "behavior_wired": True,
            "runtime_effect": "optional_enrichment_eligibility_and_evidence_threshold" if name != "adaptive" else "optional_enrichment_eligibility_guidance_and_evidence_threshold",
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
        "readiness": score_readiness(connections),
        "insights": ((latest.data or [{}])[0].get("results") or {}).get("insights", []),
        "recommendations": ((latest.data or [{}])[0].get("results") or {}).get("recommendations") or cards.get("recommendations") or [],
        "actions": ((latest.data or [{}])[0].get("results") or {}).get("actions", []),
        "outcomes": ((latest.data or [{}])[0].get("results") or {}).get("outcomes", []),
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
                      org_id, metadata={"previous": previous, "current": merged, "router_policy_applied": True})
    return {"capabilities": _settings(merged), "saved": bool(result.data),
            "router_policy_applied": "adaptive" in body.capabilities, "advisory_only": True}


@router.post("/sweeps", status_code=202)
def request_sweep(
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict:
    if os.getenv("INTELLIGENCE_OVERVIEW_SWEEP_WORKER_ENABLED", "").lower() not in {"1", "true"}:
        raise HTTPException(status_code=503, detail="Intelligence sweep worker is not enabled.")
    # Queue the intent durably. No ingestion is started or implied: worker activation
    # requires an audited connector permission + orchestration implementation.
    client = _db(settings)
    connections = load_connected_connectors(client, org_id)
    vendors = sorted({c["vendor"] for c in connections if c.get("executable")})
    if not vendors:
        raise HTTPException(status_code=409, detail="Connect at least one usable data source first.")
    from app.billing.intelligence_sweep_meter import reserve_sweep
    sweep = reserve_sweep(
        client, org_id, _actor(admin) or None,
        {"vendors_requested": vendors, "connector_count": len(vendors)},
    )
    write_audit_event(client, org_id, _actor(admin), "intelligence.overview.sweep_requested",
                      "intelligence_overview_sweep", str(sweep["id"]),
                      metadata={"vendors_requested": vendors, "execution_started": False})
    return {"sweep": sweep, "started": False, "orchestrator_enabled": False,
            "message": "Queued for limited integration telemetry assessment; historical business-data analysis is not yet available."}


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


@router.get("/action-candidates")
def action_candidates(
    member: Annotated[tuple, Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Settings = Depends(get_settings),
) -> dict:
    """Canonical Play readiness/read-only workflow bindings.

    This discovers possible handoffs, never treats recommendations as consent
    or calls the Play run endpoint.
    """
    from app.routers.plays import list_plays

    result = list_plays(member, environment_name, settings)
    candidates = []
    for item in result.get("plays") or []:
        play = item.get("play") or {}
        readiness = item.get("readiness") or {}
        candidates.append({
            "play": play,
            "readiness": readiness,
            "installation": item.get("installation"),
            "workflowBindings": item.get("workflowBindings") or [],
            "href": "/plays",
            "executionAuthority": "canonical_workflow_runtime",
            "advisoryOnly": True,
        })
    return {"candidates": candidates, "count": len(candidates),
            "advisoryOnly": True, "executes": False,
            "requiresExistingPlayApprovalAndPermissions": True}


def _verified_evidence_recommendations(client, org_id: str) -> list[dict]:
    """Re-derive IDs from persisted tenant evidence, never trust client claims."""
    from app.services.intelligence_evidence_recommendations import build_evidence_recommendations
    records = (client.table("intelligence_history_records")
               .select("org_id,connector_id,object_type,external_id")
               .eq("org_id", org_id).limit(2000).execute()).data or []
    matches = (client.table("intelligence_entity_matches")
               .select("org_id,identity_kind,identity_hash,match_status,record_references")
               .eq("org_id", org_id).limit(1000).execute()).data or []
    # No partial recommendation if a bounded read cannot prove full evidence.
    if len(records) >= 2000 or len(matches) >= 1000:
        raise HTTPException(status_code=409, detail="Evidence index too large for bounded assessment.")
    return build_evidence_recommendations(records, matches, org_id=org_id)


@router.get("/evidence-recommendations")
def evidence_recommendations(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict:
    items = _verified_evidence_recommendations(_db(settings), org_id)
    return {"recommendations": items, "count": len(items), "advisoryOnly": True,
            "executionAuthority": "canonical_play_runtime",
            "requiresApproval": True}


class RecommendationPlayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: str = Field(min_length=1)


@router.post("/evidence-recommendations/{recommendation_id}/play-runs")
async def execute_evidence_recommendation(
    recommendation_id: str,
    body: RecommendationPlayRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Settings = Depends(get_settings),
) -> dict:
    """Only initiate canonical Play execution; workflows own approval/write gates."""
    from app.routers.plays import RunPlayRequest, run_play
    client = _db(settings)
    recommendation = next(
        (r for r in _verified_evidence_recommendations(client, org_id)
         if r["id"] == recommendation_id), None,
    )
    if not recommendation:
        raise HTTPException(status_code=404, detail="Evidence recommendation not found")
    play_key = recommendation["recommended_play_key"]
    # Durable claim BEFORE invoking canonical execution: concurrent submissions
    # cannot initiate duplicate Plays. Failed/ambiguous handoffs need manual
    # reconciliation; never automatically retry an external write.
    try:
        claimed = client.table("intelligence_recommendation_play_links").insert({
            "org_id": org_id, "recommendation_id": recommendation_id,
            "installation_id": body.installation_id, "play_key": play_key,
            "created_by": _actor(admin) or None, "status": "submitting",
        }).execute()
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Recommendation handoff already claimed or unavailable") from exc
    link = (claimed.data or [None])[0]
    if not link or not link.get("id"):
        raise HTTPException(status_code=503, detail="Could not persist recommendation handoff")
    try:
        # Canonical Play runtime verifies installation ownership, readiness,
        # every bound workflow's approval policy, and membership.
        result = await run_play(
            play_key, RunPlayRequest(installationId=body.installation_id),
            admin, environment_name, settings,
        )
        runs = [str(item.get("runId")) for item in (result.get("workflowRuns") or [])
                if item.get("runId")]
        receipt = (client.table("intelligence_recommendation_play_links").update({
            "status": "submitted",
            "play_run_id": result.get("playRunId"),
            "workflow_run_ids": runs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("org_id", org_id).eq("id", str(link["id"])).execute())
        if not receipt.data:
            raise RuntimeError("Attribution write unavailable")
    except Exception:
        # Fail closed: a partial Play start might already exist; do not retry.
        try:
            client.table("intelligence_recommendation_play_links").update({
                "status": "handoff_error",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("org_id", org_id).eq("id", str(link["id"])).execute()
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Play handoff requires reconciliation; do not retry automatically")

    return {"recommendationId": recommendation_id, "playKey": play_key,
            "playRun": result, "handoffId": str(link["id"]), "approvalBypass": False,
            "outcomesHref": f"/api/plays/{play_key}/outcomes",
            "evidenceHrefTemplate": f"/api/plays/{play_key}/outcomes/{{outcome_id}}/evidence",
            "verifiedBusinessOutcome": False}


@router.get("/evidence-recommendations/{recommendation_id}/handoffs")
def evidence_recommendation_handoffs(
    recommendation_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict:
    """Read back persisted Play attribution and source-verified business results."""
    from app.plays.outcomes import list_play_business_results
    from app.plays.evidence import build_play_evidence_chain
    from app.services.intelligence_outcome_verification import verified_business_evidence
    client = _db(settings)
    links = (client.table("intelligence_recommendation_play_links")
             .select("id,org_id,recommendation_id,play_key,play_run_id,workflow_run_ids,status,created_at")
             .eq("org_id", org_id).eq("recommendation_id", recommendation_id)
             .limit(50).execute()).data or []
    if not links:
        return {"recommendationId": recommendation_id, "handoffs": [], "count": 0}
    completed = []
    for link in links:
        workflow_ids = set(str(x) for x in (link.get("workflow_run_ids") or []) if x)
        outcomes = []
        if workflow_ids:
            candidates = list_play_business_results(
                client, org_id, play_key=str(link["play_key"]), limit=200,
            )
            for outcome in candidates:
                if str(outcome.get("workflow_run_id") or "") not in workflow_ids:
                    continue
                metadata = outcome.get("metadata") or {}
                status_value = str(metadata.get("verification_state") or "")
                verified = status_value in {"VERIFIED SUCCESS", "VERIFIED FAILURE"}
                source_evidence = (build_play_evidence_chain(
                    client, org_id, str(outcome["id"]), play_key=str(link["play_key"]),
                ) if verified else None)
                outcomes.append({
                    "outcomeId": str(outcome["id"]),
                    "verificationState": status_value or "UNKNOWN",
                    "verified": verified_business_evidence(status_value, source_evidence),
                    "evidence": source_evidence,
                })
        completed.append({
            "handoffId": str(link["id"]),
            "playKey": str(link["play_key"]),
            "playRunId": link.get("play_run_id"),
            "status": link.get("status"),
            "outcomes": outcomes,
            "verifiedBusinessOutcome": any(item["verified"] for item in outcomes),
        })
    return {"recommendationId": recommendation_id, "handoffs": completed,
            "count": len(completed)}


@router.get("/sweep-usage")
def intelligence_sweep_usage(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict:
    """Read-only quota, scoped to authenticated member's organization."""
    from app.billing.intelligence_sweep_meter import sweep_usage_snapshot
    return sweep_usage_snapshot(_db(settings), org_id)
