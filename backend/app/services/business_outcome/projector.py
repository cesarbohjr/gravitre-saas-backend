"""Project Module A / run substrates into a BusinessOutcome DTO (read-only)."""
from __future__ import annotations

from typing import Any

from app.services.business_outcome.catalog_reversal import (
    supports_vendor_diff,
    undo_availability,
)
from app.services.business_outcome.models import (
    ApprovalSection,
    BusinessOutcome,
    BusinessOutcomeKind,
    BusinessOutcomeSections,
    DiffSection,
    EvidenceSection,
    LifecycleState,
    OutcomeLink,
    RecommendationSection,
    TimelineStep,
    UndoSection,
    VerificationSection,
)
from app.services.execution_outcome import OUTCOME_SCHEMA_VERSION


def project_business_outcome(
    *,
    org_id: str,
    run: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    execution_result: dict[str, Any] | None = None,
    recommendation: dict[str, Any] | None = None,
    invoke_action: str | None = None,
    compensation_snapshot: dict[str, Any] | None = None,
    notification_emitted: bool = False,
    module_a_schema_version: str | None = None,
) -> BusinessOutcome:
    """Derive one BusinessOutcome. Never invent section content."""
    run = run or {}
    er = execution_result or {}
    params = run.get("parameters") if isinstance(run.get("parameters"), dict) else {}
    snapshot = (
        run.get("definition_snapshot")
        if isinstance(run.get("definition_snapshot"), dict)
        else {}
    )
    run_id = str(run.get("id") or er.get("entity_id") or "").strip() or None
    conversation_id = (
        str(params.get("conversation_id") or params.get("conversationId") or "").strip()
        or str((er.get("structured") or {}).get("conversationId") or "").strip()
        or None
    )
    status = str(run.get("status") or ("completed" if er.get("success") else "failed") or "unknown")
    source = str(params.get("source") or snapshot.get("source") or er.get("integration") or "unknown")
    title = str(
        er.get("task_label")
        or er.get("title")
        or params.get("label")
        or snapshot.get("name")
        or "Completed work"
    )
    summary = str(er.get("body") or run.get("error_message") or params.get("summary") or "").strip() or None
    if not summary and run.get("error_message"):
        summary = str(run.get("error_message"))

    kind = _infer_kind(status=status, invoke_action=invoke_action, params=params, er=er)
    evidence = _evidence(er, run_id=run_id)
    verification = _verification(er, status=status)
    explanation = _explanation(er, run)
    timeline = _timeline(steps or params.get("step_results") or [])
    approval = _approval(run)
    recs = _recommendations(recommendation or er.get("recommendation"))
    action = invoke_action or str(params.get("invoke_action") or params.get("invokeAction") or "")
    undo = _undo(action)
    diff = _diff(action, compensation_snapshot)

    lifecycle_reached = _lifecycle_reached(
        status=status,
        verified=bool(verification and verification.verified),
        presented=notification_emitted or bool(er),
        approved=bool(approval and str(approval.status).lower() in {"approved", "not_required"}),
        undone=str(status).lower() in {"rolled_back", "compensated", "undone"},
    )
    lifecycle_state = lifecycle_reached[-1] if lifecycle_reached else "created"

    sections = BusinessOutcomeSections(
        summary=summary,
        impact=None,
        evidence=evidence,
        verification=verification,
        explanation=explanation,
        timeline=timeline or None,
        related_outcomes=None,
        dependencies=None,
        recommendations=recs or None,
        history=None,
        approval=approval,
        diff=diff,
        undo=undo,
        metadata={
            "source": source,
            "integration": er.get("integration") or params.get("integration"),
            "invokeAction": action or None,
            "errorCode": er.get("error_code"),
        },
    )

    return BusinessOutcome(
        id=run_id or str(er.get("entity_id") or conversation_id or "unknown"),
        org_id=org_id,
        kind=kind,
        title=title,
        status=status,
        lifecycle_state=lifecycle_state,  # type: ignore[arg-type]
        lifecycle_states_reached=lifecycle_reached,  # type: ignore[arg-type]
        source=source,
        created_at=str(run.get("created_at") or run.get("started_at") or "") or None,
        sections=sections,
        pipeline_stages_completed=[],
        module_a_schema_version=module_a_schema_version or OUTCOME_SCHEMA_VERSION,
        run_id=run_id,
        conversation_id=conversation_id,
    )


def _infer_kind(
    *,
    status: str,
    invoke_action: str | None,
    params: dict[str, Any],
    er: dict[str, Any],
) -> BusinessOutcomeKind:
    if str(status).lower() in {"failed", "error", "cancelled"}:
        return "failed_action"
    if str(params.get("source") or "").startswith("swarm") or er.get("entity_type") == "swarm_run":
        return "completed_swarm"
    action = str(invoke_action or "").lower()
    if ".create" in action or "lists.create" in action:
        return "created_record"
    if ".update" in action:
        return "updated_record"
    if params.get("step_results") or params.get("orchestration_run_id"):
        return "completed_workflow"
    if er.get("recommendation") or params.get("kind") == "recommendation":
        return "recommendation"
    return "other"


def _evidence(er: dict[str, Any], *, run_id: str | None) -> EvidenceSection | None:
    links: list[OutcomeLink] = []
    result_url = str(er.get("result_url") or "").strip()
    external = str(er.get("external_url") or "").strip()
    structured = er.get("structured") if isinstance(er.get("structured"), dict) else {}
    if not external:
        external = str(structured.get("external_url") or "").strip()
    if result_url:
        links.append(OutcomeLink(label="View in Gravitre", href=result_url, kind="gravitre"))
    if external.startswith("http"):
        vendor = str(er.get("integration") or "vendor").title()
        links.append(OutcomeLink(label=f"View in {vendor}", href=external, kind="vendor"))
    if run_id and not any(link.href.startswith("/runs/") for link in links):
        links.append(OutcomeLink(label="View run", href=f"/runs/{run_id}", kind="gravitre"))
    entity_type = str(er.get("entity_type") or structured.get("entity_type") or "") or None
    entity_id = str(er.get("entity_id") or structured.get("entity_id") or "") or None
    if not links and not entity_id:
        return None
    return EvidenceSection(
        links=links,
        entity_type=entity_type,
        entity_id=entity_id,
        integration=str(er.get("integration") or "") or None,
    )


def _verification(er: dict[str, Any], *, status: str) -> VerificationSection | None:
    if str(status).lower() in {"failed", "error", "cancelled"}:
        return VerificationSection(
            verified=False,
            method="module_a_terminal_status",
            detail="Outcome terminated without successful verification.",
        )
    body = str(er.get("body") or "").strip()
    external = str(er.get("external_url") or "").strip()
    result_url = str(er.get("result_url") or "").strip()
    if body or external or result_url:
        return VerificationSection(
            verified=True,
            method="module_a_verified_output",
            detail="Non-empty summary and/or result link present on Module A verified output.",
        )
    return None


def _explanation(er: dict[str, Any], run: dict[str, Any]) -> str | None:
    means = er.get("what_this_means") or (er.get("structured") or {}).get("whatThisMeans")
    if means:
        return str(means)
    err = run.get("error_message") or er.get("body")
    if er.get("success") is False and err:
        return str(err)
    return None


def _timeline(raw_steps: list[Any]) -> list[TimelineStep]:
    steps: list[TimelineStep] = []
    for idx, row in enumerate(raw_steps):
        if not isinstance(row, dict):
            continue
        steps.append(
            TimelineStep(
                index=idx + 1,
                label=str(row.get("label") or row.get("name") or f"Step {idx + 1}"),
                status=str(row.get("status") or ("completed" if row.get("success") else "unknown")),
                summary=str(row.get("summary") or row.get("error") or row.get("body") or "")[:500]
                or None,
                evidence_url=str(
                    row.get("external_url") or row.get("url") or row.get("result_url") or ""
                )
                or None,
                agent_name=str(row.get("agentName") or row.get("agent_name") or "") or None,
            )
        )
    return steps


def _approval(run: dict[str, Any]) -> ApprovalSection | None:
    status = run.get("approval_status") or run.get("approvalStatus")
    if not status:
        return None
    return ApprovalSection(
        status=str(status),
        required=run.get("required_approvals") or run.get("requiredApprovals"),
        received=run.get("approvals_received") or run.get("approvalsReceived"),
    )


def _recommendations(raw: Any) -> list[RecommendationSection]:
    if not isinstance(raw, dict):
        return []
    if not raw.get("title"):
        return []
    return [
        RecommendationSection(
            title=str(raw["title"]),
            reason=str(raw.get("reason") or ""),
            suggested_utterance=str(raw.get("suggestedUtterance") or raw.get("suggested_utterance") or "")
            or None,
            advisory_only=True,
            href=str(raw.get("href") or "") or None,
            confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
            confidence_is_estimate=bool(
                raw.get("confidence_is_estimate", raw.get("confidenceIsEstimate", True))
            ),
        )
    ]


def _undo(invoke_action: str) -> UndoSection | None:
    if not invoke_action:
        return None
    info = undo_availability(invoke_action)
    return UndoSection(
        available=bool(info["available"]),
        compensating_action=info.get("compensating_action"),
        honest_unavailable_reason=info.get("honest_unavailable_reason"),
    )


def _diff(invoke_action: str, snapshot: dict[str, Any] | None) -> DiffSection | None:
    if not invoke_action:
        return None
    if not supports_vendor_diff(invoke_action):
        return DiffSection(
            available=False,
            prior=None,
            note="No vendor prior-value snapshot path is declared for this action in the catalog.",
        )
    if not snapshot:
        return DiffSection(
            available=False,
            prior=None,
            note="Diff is supported for this action, but no prior snapshot was captured for this run.",
        )
    return DiffSection(available=True, prior=dict(snapshot), note=None)


def _lifecycle_reached(
    *,
    status: str,
    verified: bool,
    presented: bool,
    approved: bool,
    undone: bool,
) -> list[LifecycleState]:
    reached: list[LifecycleState] = ["created"]
    if verified:
        reached.append("verified")
    if presented:
        reached.append("presented")
    if approved:
        reached.append("approved")
    if undone:
        reached.append("undone")
    return reached
