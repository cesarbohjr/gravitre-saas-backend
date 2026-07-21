"""BusinessOutcome API — one projection shape for every consumer.

No consumer-specific branching: chat, timeline, export, and future surfaces
all receive the same DTO from these endpoints.
"""
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.services.business_outcome.pipeline import PipelineContext, run_business_outcome_pipeline
from app.workflows.repository import get_run_with_steps, get_supabase_client

router = APIRouter(prefix="/api/business-outcomes", tags=["business-outcomes"])


@router.get("")
async def list_business_outcomes(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    integration: str | None = Query(default=None),
    lifecycle_state: str | None = Query(default=None, alias="lifecycleState"),
) -> dict[str, Any]:
    """List projected outcomes — same DTO shape as detail (no consumer branching)."""
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    q = (
        client.table("workflow_runs")
        .select(
            "id, status, approval_status, required_approvals, created_at, completed_at, "
            "error_message, parameters, definition_snapshot, environment"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status_filter:
        q = q.eq("status", status_filter)
    rows = list((q.execute().data or []))
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            dto = _project_from_run(client, org_id, str(row["id"]), environment_name)
        except HTTPException:
            continue
        if integration:
            meta = (dto.get("sections") or {}).get("metadata") or {}
            if str(meta.get("integration") or "").lower() != integration.lower():
                continue
        if lifecycle_state and dto.get("lifecycleState") != lifecycle_state:
            continue
        items.append(dto)
    return {"businessOutcomes": items, "count": len(items)}


def _project_from_run(
    client: Any,
    org_id: str,
    run_id: str,
    environment_name: str,
) -> dict[str, Any]:
    run_payload = get_run_with_steps(client, org_id, run_id, environment_name)
    if not run_payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outcome not found")
    steps = list(run_payload.pop("steps", []) or [])
    params = run_payload.get("parameters") if isinstance(run_payload.get("parameters"), dict) else {}
    invoke_action = str(params.get("invoke_action") or params.get("invokeAction") or "") or None
    # Prefer Module A verified fields from parameters / snapshot when present.
    verified = params.get("verified_output") if isinstance(params.get("verified_output"), dict) else {}
    execution_result = {
        "success": str(run_payload.get("status") or "").lower()
        in {"completed", "success", "succeeded"},
        "title": params.get("label") or run_payload.get("error_message") or "Completed work",
        "body": verified.get("summary")
        or params.get("summary")
        or run_payload.get("error_message")
        or "",
        "result_url": verified.get("result_url") or f"/runs/{run_id}",
        "external_url": verified.get("external_url"),
        "integration": verified.get("integration") or params.get("integration"),
        "entity_type": verified.get("entity_type") or "workflow_run",
        "entity_id": verified.get("entity_id") or run_id,
        "error_code": params.get("error_code"),
        "recommendation": params.get("recommendation"),
        "what_this_means": params.get("what_this_means") or params.get("whatThisMeans"),
        "structured": {
            "conversationId": params.get("conversation_id") or params.get("conversationId"),
            "step_results": params.get("step_results") or [],
            "external_url": verified.get("external_url"),
        },
    }
    notification_emitted = bool(params.get("notification_emitted") or params.get("notified"))
    outcome = run_business_outcome_pipeline(
        PipelineContext(
            org_id=org_id,
            run=run_payload,
            steps=steps,
            execution_result=execution_result,
            invoke_action=invoke_action,
            notification_emitted=notification_emitted,
        )
    )
    return outcome.to_dict()


@router.get("/{outcome_id}")
async def get_business_outcome(
    outcome_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Single BusinessOutcome DTO. Identity today is Module A run_id."""
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    dto = _project_from_run(client, org_id, str(outcome_id), environment_name)
    return {"businessOutcome": dto}


@router.post("/{outcome_id}/undo")
async def undo_business_outcome(
    outcome_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Governed undo — same compensate path as runs; catalog_write_authority enforced."""
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    # Surface honesty: if catalog has no compensating action, refuse before invoke.
    client = get_supabase_client(settings)
    dto = _project_from_run(client, org_id, str(outcome_id), environment_name)
    undo = (dto.get("sections") or {}).get("undo") or {}
    if not undo.get("available"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=undo.get("honestUnavailableReason")
            or "Undo is not available for this outcome (no catalog compensating action).",
        )
    from app.services.compensation_service import execute_compensations, notify_compensation_webhook

    summary = execute_compensations(
        client,
        settings,
        org_id=org_id,
        run_id=str(outcome_id),
        actor_id=current_user["user_id"],
        environment_name=environment_name,
    )
    if summary.get("compensated") or summary.get("failed"):
        notify_compensation_webhook(
            client,
            settings,
            org_id=org_id,
            run_id=str(outcome_id),
            actor_id=current_user["user_id"],
            summary=summary,
            environment_name=environment_name,
        )
    return {"businessOutcomeId": str(outcome_id), "undo": summary}


@router.get("/{outcome_id}/export")
async def export_business_outcome(
    outcome_id: UUID,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    format: str = Query(default="json", pattern="^(json|markdown)$"),
) -> Any:
    """Serialize the same DTO for shareable export (no alternate business content)."""
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    dto = _project_from_run(client, org_id, str(outcome_id), environment_name)
    if format == "json":
        return {"businessOutcome": dto, "exportFormat": "json"}
    lines = [
        f"# {dto.get('title')}",
        "",
        f"Status: {dto.get('status')}",
        f"Lifecycle: {dto.get('lifecycleState')}",
        f"Kind: {dto.get('kind')}",
        "",
    ]
    sections = dto.get("sections") or {}
    if sections.get("summary"):
        lines.extend(["## Summary", sections["summary"], ""])
    if sections.get("explanation"):
        lines.extend(["## Explanation", sections["explanation"], ""])
    if sections.get("verification"):
        lines.extend(["## Verification", json.dumps(sections["verification"], indent=2), ""])
    if sections.get("evidence"):
        lines.extend(["## Evidence", json.dumps(sections["evidence"], indent=2), ""])
    if sections.get("timeline"):
        lines.append("## Timeline")
        for step in sections["timeline"]:
            lines.append(
                f"- {step.get('index')}. {step.get('label')} ({step.get('status')}): "
                f"{step.get('summary') or ''}"
            )
        lines.append("")
    if sections.get("recommendations"):
        lines.append("## Recommendations (suggest-only)")
        for rec in sections["recommendations"]:
            lines.append(f"- {rec.get('title')}: {rec.get('reason')}")
        lines.append("")
    if sections.get("undo"):
        lines.extend(["## Undo", json.dumps(sections["undo"], indent=2), ""])
    if sections.get("diff"):
        lines.extend(["## Diff", json.dumps(sections["diff"], indent=2), ""])
    body = "\n".join(lines)
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
