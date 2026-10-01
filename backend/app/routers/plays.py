"""Read-only Play catalog/readiness API.

Execution remains in canonical workflows. This router does not execute Plays
or mutate connector/workflow/governance state.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_environment_context, require_admin, require_org_member
from app.capabilities.registry import connected_vendors
from app.config import Settings, get_settings
from app.plays.catalog import PLATFORM_PLAY_TEMPLATES, get_platform_play
from app.plays.customer_rescue import observe_customer_rescue
from app.plays.evidence import build_play_evidence_chain
from app.plays.marketing_performance import list_marketing_performance_signals
from app.plays.outcomes import list_play_business_results
from app.plays.readiness import resolve_play_readiness
from app.plays.revenue_recovery import list_revenue_recovery_signals
from app.plays.workflow_bindings import (
    bind_play_to_workflow,
    list_play_workflow_bindings,
    unbind_play_from_workflow,
)
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client, get_workflow_def\nfrom app.workflows.policy import resolve_policy, PolicyResolutionError

router = APIRouter(prefix="/api/plays", tags=["plays"])

class RunPlayRequest(BaseModel):\n    installation_id: str = Field(..., alias="installationId", min_length=1)\n\n    model_config = {"populate_by_name": True}\n\n\nclass BindWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., alias="workflowId", min_length=1)

    model_config = {"populate_by_name": True}



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
        bindings = list_play_workflow_bindings(client, org_id, play.key)
        items.append(
            {
                "play": _template_payload(play),
                "readiness": readiness.as_dict(),
                "workflowBindings": bindings,
                "workflowBindingCount": len(bindings),
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






@router.get("/customer-rescue/observe")
async def observe_customer_rescue_play(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    play = get_platform_play("customer-rescue")
    assert play is not None
    connected = connected_vendors(client, org_id, environment_name)
    readiness = resolve_play_readiness(
        play,
        connected_vendors=connected,
        client=client,
        org_id=org_id,
        policy_authorized_actions=set(),
    )
    observed = await observe_customer_rescue(
        org_id,
        settings=settings,
        client=client,
        limit=limit,
    )
    return {
        "playKey": play.key,
        "readiness": readiness.as_dict(),
        **observed,
    }


@router.get("/marketing-performance/observe")
async def observe_marketing_performance(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    play = get_platform_play("marketing-performance")
    assert play is not None
    connected = connected_vendors(client, org_id, environment_name)
    readiness = resolve_play_readiness(
        play,
        connected_vendors=connected,
        client=client,
        org_id=org_id,
        policy_authorized_actions=set(),
    )
    signals = list_marketing_performance_signals(client, org_id, limit=limit)
    return {
        "playKey": play.key,
        "mode": "OBSERVE",
        "readiness": readiness.as_dict(),
        "signals": signals,
        "count": len(signals),
        "actionTaken": False,
        "truthRule": (
            "Marketing performance movement is not pipeline or revenue attribution. "
            "Business impact requires source-linked outcome evidence."
        ),
    }


@router.get("/revenue-recovery/observe")
async def observe_revenue_recovery(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Read existing revenue-recovery signals without taking external action."""
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    play = get_platform_play("revenue-recovery")
    assert play is not None
    connected = connected_vendors(client, org_id, environment_name)
    readiness = resolve_play_readiness(
        play,
        connected_vendors=connected,
        client=client,
        org_id=org_id,
        policy_authorized_actions=set(),
    )
    signals = list_revenue_recovery_signals(client, org_id, limit=limit)
    return {
        "playKey": play.key,
        "mode": "OBSERVE",
        "readiness": readiness.as_dict(),
        "signals": signals,
        "count": len(signals),
        "actionTaken": False,
        "verifiedRecoveredRevenue": None,
        "truthRule": (
            "Detected overdue invoices or stalled deals are opportunities, not recovered revenue. "
            "Recovered revenue is reported only after source-of-record verification."
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
    bindings = list_play_workflow_bindings(client, org_id, play.key)
    return {
        "play": _template_payload(play),
        "readiness": readiness.as_dict(),
        "workflowBindings": bindings,
        "workflowBindingCount": len(bindings),
        "executionAuthority": "canonical_workflow_runtime",
    }






@router.post("/{play_key}/runs")
async def run_play(
    play_key: str,
    body: RunPlayRequest,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Start a Play by delegating each bound workflow to canonical execution.

    ACT WITH APPROVAL is fail-closed: every bound workflow must already require
    approval under canonical workflow policy before any workflow is started.
    """
    user, org_id, _role = member
    play = get_platform_play(play_key)
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    client = get_supabase_client(settings)
    rows = (
        client.table("play_installations")
        .select("*")
        .eq("id", body.installation_id)
        .eq("org_id", org_id)
        .eq("play_key", play.key)
        .eq("environment_name", environment_name)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play setup not found")
    installation = dict(rows[0])
    mode = str(installation.get("operating_mode") or "OBSERVE")
    if mode not in {"ACT WITH APPROVAL", "ACT WITHIN POLICY"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This operating mode does not permit external actions. Choose an action mode after readiness is satisfied.",
        )

    connected = connected_vendors(client, org_id, environment_name)
    readiness = resolve_play_readiness(
        play,
        connected_vendors=connected,
        client=client,
        org_id=org_id,
        policy_authorized_actions=set(),
    )
    if mode == "ACT WITH APPROVAL" and not readiness.act_with_approval_ready:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Play is not ready to act with approval")
    if mode == "ACT WITHIN POLICY":
        # Slice 4 deliberately fails closed until effective action-level policy
        # authorization can be proven for this concrete execution context.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Act within policy requires effective runtime action authorization and is not available for this Play run yet.",
        )

    bindings = list_play_workflow_bindings(client, org_id, play.key)
    if not bindings:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No workflows are linked to this Play")

    # Preflight every workflow before starting any of them. This prevents a
    # partially-started Play when one workflow lacks the required approval gate.
    for binding in bindings:
        workflow_id = str(binding.get("workflowId") or "")
        workflow = get_workflow_def(client, org_id, workflow_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Linked workflow {workflow_id} no longer exists")
        try:
            required_approvals, _roles = resolve_policy(client, org_id, workflow_id, "execute")
        except PolicyResolutionError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workflow policy resolution failed") from exc
        if required_approvals < 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Linked workflow {workflow_id} must require approval before this Play can run in Act with approval mode",
            )

    from uuid import uuid4
    from app.routers.workflows import ExecuteRequest, execute_workflow

    play_run_id = str(uuid4())
    client.table("play_runs").insert({
        "id": play_run_id,
        "org_id": org_id,
        "installation_id": body.installation_id,
        "play_key": play.key,
        "play_version": play.version,
        "operating_mode": mode,
        "trigger_type": "manual",
        "status": "running",
        "workflow_run_ids": [],
        "created_by": user.get("user_id"),
        "started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "metadata": {"execution_authority": "canonical_workflow_runtime"},
    }).execute()

    workflow_runs: list[dict[str, Any]] = []
    run_ids: list[str] = []
    try:
        for binding in bindings:
            workflow_id = str(binding.get("workflowId") or "")
            result = await execute_workflow(
                ExecuteRequest(
                    workflow_id=workflow_id,
                    playKey=play.key,
                    parameters={
                        "play": {
                            "key": play.key,
                            "version": play.version,
                            "installation_id": body.installation_id,
                            "run_id": play_run_id,
                            "operating_mode": mode,
                            "execution_authority": "canonical_workflow_runtime",
                        }
                    },
                ),
                current_user=user,
                org_id=org_id,
                environment_name=environment_name,
                settings=settings,
            )
            workflow_run_id = str(result.get("run_id") or "")
            if workflow_run_id:
                run_ids.append(workflow_run_id)
            workflow_runs.append({
                "workflowId": workflow_id,
                "runId": workflow_run_id,
                "status": result.get("status"),
                "approvalRequired": bool(result.get("approval_required")),
            })
        aggregate_status = "awaiting_approval" if any(row["approvalRequired"] for row in workflow_runs) else "running"
        client.table("play_runs").update({
            "workflow_run_ids": run_ids,
            "status": aggregate_status,
        }).eq("id", play_run_id).eq("org_id", org_id).execute()
    except Exception:
        client.table("play_runs").update({
            "workflow_run_ids": run_ids,
            "status": "partial_success" if run_ids else "failed",
        }).eq("id", play_run_id).eq("org_id", org_id).execute()
        raise

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user.get("user_id"),
        action="play.run.started",
        resource_type="play_run",
        resource_id=play_run_id,
        metadata={
            "play_key": play.key,
            "installation_id": body.installation_id,
            "operating_mode": mode,
            "workflow_run_ids": run_ids,
            "execution_authority": "canonical_workflow_runtime",
        },
    )
    return {
        "playRunId": play_run_id,
        "status": aggregate_status,
        "operatingMode": mode,
        "workflowRuns": workflow_runs,
        "executionAuthority": "canonical_workflow_runtime",
    }


@router.get("/{play_key}/workflow-bindings")
async def get_play_workflow_bindings(
    play_key: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    play = get_platform_play(play_key)
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    bindings = list_play_workflow_bindings(client, org_id, play.key)
    return {
        "playKey": play.key,
        "workflowBindings": bindings,
        "count": len(bindings),
        "executionAuthority": "canonical_workflow_runtime",
    }


@router.post("/{play_key}/workflow-bindings")
async def create_play_workflow_binding(
    play_key: str,
    body: BindWorkflowRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = get_supabase_client(settings)
    try:
        binding = bind_play_to_workflow(
            client,
            org_id,
            play_key=play_key,
            workflow_id=body.workflow_id,
            actor_id=str(user.get("user_id") or "") or None,
            environment_name=environment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user.get("user_id"),
        action="play.workflow.bound",
        resource_type="workflow",
        resource_id=body.workflow_id,
        metadata={
            "play_key": play_key,
            "environment": environment_name,
            "execution_authority": "canonical_workflow_runtime",
        },
    )
    return binding


@router.delete("/{play_key}/workflow-bindings/{workflow_id}")
async def delete_play_workflow_binding(
    play_key: str,
    workflow_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = get_supabase_client(settings)
    try:
        result = unbind_play_from_workflow(
            client,
            org_id,
            play_key=play_key,
            workflow_id=workflow_id,
            environment_name=environment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user.get("user_id"),
        action="play.workflow.unbound",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={"play_key": play_key, "environment": environment_name},
    )
    return result


@router.get("/{play_key}/outcomes/{outcome_id}/evidence")
async def get_play_outcome_evidence(
    play_key: str,
    outcome_id: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    play = get_platform_play(play_key)
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    org_id = _member_org(member)
    client = get_supabase_client(settings)
    chain = build_play_evidence_chain(
        client,
        org_id,
        outcome_id,
        play_key=play.key,
    )
    if chain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Play business result not found",
        )
    return {
        "playKey": play.key,
        "evidence": chain,
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
