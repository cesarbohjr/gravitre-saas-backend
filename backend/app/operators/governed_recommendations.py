"""Fail-closed operator recommendation confirmation, using canonical workflow execution.

Only workflow references can be proposed. This endpoint never calls providers directly and
never reports provider completion from a workflow enqueue. A claimed recommendation is
single-use even when downstream execution errors; an operator must reconcile uncertainty.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, get_environment_context
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.routers.workflows import _execute_workflow_with_context

router = APIRouter()
_ALLOWED_TYPES = {"workflow-param-suggester"}
_ALLOWED_STATES = {"pending", "claimed", "rejected", "running", "pending_approval", "verification_inconclusive"}


class RecommendationRequest(BaseModel):
    workflow_id: UUID
    parameters: dict = Field(default_factory=dict)


class ConfirmationRequest(BaseModel):
    recommendation_id: UUID
    confirmed: bool


def _require_org(org_id: str | None, user: dict) -> str:
    if not org_id or not user.get("user_id"):
        raise HTTPException(403, "Organization and authenticated user required")
    return org_id


def _single_claim(client, *, rec_id: str, org_id: str, operator_type: str, status: str, user_id: str):
    # Both predicate and UPDATE execute in one database statement; a concurrent caller
    # must observe no returned row. Expiry is checked in the same statement.
    now = datetime.now(timezone.utc).isoformat()
    result = (
        client.table("operator_recommendations")
        .update({"status": status, "confirmed_by": user_id, "updated_at": now})
        .eq("id", rec_id).eq("org_id", org_id)
        .eq("operator_type", operator_type).eq("created_by", user_id).eq("status", "pending")
        .gt("expires_at", now).select("id, recommendation, status").execute()
    )
    rows = result.data or []
    if len(rows) != 1:
        raise HTTPException(409, "Recommendation unavailable, expired, or already claimed")
    return rows[0]


@router.post("/{operator_type}/recommend")
def recommend(
    operator_type: str,
    body: RecommendationRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    org = _require_org(org_id, user)
    if operator_type not in _ALLOWED_TYPES:
        raise HTTPException(422, "Operator type does not support governed workflow recommendations")
    client = shared_service_client(settings, create_client)
    # Verify exact org ownership before storing a trusted server-side workflow reference.
    rows = client.table("workflow_defs").select("id").eq("org_id", org).eq("id", str(body.workflow_id)).limit(1).execute().data or []
    if not rows:
        raise HTTPException(404, "Workflow not found in organization")
    plan = {"workflow_id": str(body.workflow_id), "parameters": body.parameters, "environment": environment}
    record = client.table("operator_recommendations").insert({
        "org_id": org, "operator_type": operator_type, "recommendation": plan,
        "status": "pending", "created_by": str(user["user_id"])
    }).execute().data or []
    if len(record) != 1:
        raise HTTPException(503, "Recommendation could not be stored")
    return {"recommendation_id": record[0]["id"], "status": "pending", "recommendation": plan,
            "expires_at": record[0].get("expires_at")}


@router.post("/{operator_type}/confirm")
def confirm(
    operator_type: str,
    body: ConfirmationRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    org = _require_org(org_id, user)
    if operator_type not in _ALLOWED_TYPES:
        raise HTTPException(422, "Operator type does not support governed workflow recommendations")
    client = shared_service_client(settings, create_client)
    claimed = _single_claim(client, rec_id=str(body.recommendation_id), org_id=org,
                            operator_type=operator_type, status="claimed" if body.confirmed else "rejected",
                            user_id=str(user["user_id"]))
    if not body.confirmed:
        return {"recommendation_id": str(body.recommendation_id), "status": "rejected", "verified": False}
    plan = claimed.get("recommendation") or {}
    if not isinstance(plan, dict) or plan.get("environment") != environment:
        # Never release the claim after ambiguous or invalid execution.
        raise HTTPException(409, "Recommendation environment mismatch; manual reconciliation required")
    try:
        workflow_id = str(UUID(str(plan["workflow_id"])))
        parameters = plan["parameters"]
        if not isinstance(parameters, dict):
            raise ValueError("Invalid parameters")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "Stored recommendation invalid; manual reconciliation required") from exc
    try:
        result = _execute_workflow_with_context(
            client=client, settings=settings, org_id=org, environment_name=environment,
            workflow_id=workflow_id, parameters=parameters,
            actor_id=str(user["user_id"]), trigger_type="manual",
        )
    except Exception:
        # Preserve claim: automatic retries may duplicate a write if the provider ran.
        raise HTTPException(503, "Workflow result uncertain; reconcile run before any retry")
    run_id = str(result.get("run_id") or "")
    run_status = str(result.get("status") or "running")
    if not run_id:
        raise HTTPException(503, "Workflow did not return a durable run ID; reconcile before retry")
    # Non-terminal: 'success' is NOT evidence of source-of-record verification.
    client.table("operator_recommendations").update({
        "status": "pending_approval" if run_status == "pending_approval" else "running",
        "run_id": run_id, "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", str(body.recommendation_id)).eq("org_id", org).eq("status", "claimed").execute()
    return {"recommendation_id": str(body.recommendation_id), "run_id": run_id,
            "status": "pending_approval" if run_status == "pending_approval" else "running",
            "verified": False, "message": "Started through governed workflow; completion requires independent verification"}
