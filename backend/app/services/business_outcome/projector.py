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
    evidence = _evidence(er, run_id=run_id, params=params)
    verification = _verification(
        er, status=status, invoke_action=invoke_action, params=params
    )
    explanation = _explanation(er, run)
    timeline = _timeline(steps or params.get("step_results") or params.get("connector_output_refs") or [])
    approval = _approval(run)
    recs = _recommendations(recommendation or er.get("recommendation"))
    if not recs and verification and verification.next_actions:
        recs = [
            RecommendationSection(
                title=action_line[:120],
                reason=verification.finding
                or verification.detail
                or "Review required before treating this as verified work.",
                suggested_utterance=None,
                advisory_only=True,
                href=None,
                confidence=None,
                confidence_is_estimate=True,
            )
            for action_line in verification.next_actions
        ]
    # Prefer concrete finding as summary when the run was flagged for review.
    if (
        verification
        and verification.review_state == "flagged_for_review"
        and verification.finding
    ):
        summary = verification.finding
    action = invoke_action or str(params.get("invoke_action") or params.get("invokeAction") or "")
    undo = _undo(action)
    diff = _diff(action, compensation_snapshot)

    lifecycle_reached = _lifecycle_reached(
        status=status,
        verified=bool(
            verification
            and verification.resolved_confidence == "verified"
            and str(status).lower() != "flagged_for_review"
        ),
        presented=notification_emitted or bool(er),
        approved=bool(approval and str(approval.status).lower() in {"approved", "not_required"}),
        undone=str(status).lower() in {"rolled_back", "compensated", "undone"},
    )
    lifecycle_state = lifecycle_reached[-1] if lifecycle_reached else "created"

    # Qualitative pre-action impact (low/medium/high) when stamped — never invent $.
    impact_label = params.get("estimated_impact") or params.get("estimatedImpact")
    impact_text = str(impact_label).strip() if impact_label else None

    sections = BusinessOutcomeSections(
        summary=summary,
        impact=impact_text,
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
            "actionArgs": (
                params.get("action_args")
                if isinstance(params.get("action_args"), dict)
                else (er.get("structured") or {}).get("action_args")
            ),
            # PreActionCard projection (Phase D item 18) — only when already stamped.
            "estimated_impact": params.get("estimated_impact") or params.get("estimatedImpact"),
            "risk_level": params.get("risk_level") or params.get("riskLevel"),
            "approval_reason": params.get("approval_reason") or params.get("approvalReason"),
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
    if str(status).lower() == "flagged_for_review":
        # Not a successful create — honesty state, not a net-new verified record.
        return "other"
    if str(params.get("source") or "").startswith("swarm") or er.get("entity_type") == "swarm_run":
        return "completed_swarm"
    structured = er.get("structured") if isinstance(er.get("structured"), dict) else {}
    from app.services.connector_outcome_effects import classify_write_effect

    action = str(invoke_action or params.get("invoke_action") or params.get("invokeAction") or "")
    effect = str(
        params.get("outcome_effect")
        or structured.get("outcome_effect")
        or classify_write_effect(
            invoke_action=action or None,
            result_data=structured or None,
            success=str(status).lower() in {"completed", "partial_success"},
            metadata=params,
        )
        or ""
    ).strip().lower()
    body_lower = str(er.get("body") or "").lower()
    if (
        effect in {"already_existed", "noop"}
        or params.get("already_existed") is True
        or structured.get("already_existed") is True
        or body_lower.startswith("found existing")
    ):
        return "found_existing_record"
    if effect == "accepted_async":
        return "other"
    if effect == "unknown":
        # Mutating + unproven must never surface as created_record.
        return "other"
    if effect == "updated" or ".update" in action.lower():
        return "updated_record"
    if effect == "created" or ".create" in action.lower() or "lists.create" in action.lower():
        return "created_record"
    if params.get("step_results") or params.get("orchestration_run_id"):
        return "completed_workflow"
    if er.get("recommendation") or params.get("kind") == "recommendation":
        return "recommendation"
    return "other"


def _evidence(
    er: dict[str, Any],
    *,
    run_id: str | None,
    params: dict[str, Any] | None = None,
) -> EvidenceSection | None:
    links: list[OutcomeLink] = []
    result_url = str(er.get("result_url") or "").strip()
    external = str(er.get("external_url") or "").strip()
    structured = er.get("structured") if isinstance(er.get("structured"), dict) else {}
    params = params if isinstance(params, dict) else {}
    if not external:
        external = str(structured.get("external_url") or "").strip()
    if result_url:
        if result_url.startswith("/ai?conversation="):
            result_url = result_url.replace("/ai?conversation=", "/ai?c=", 1)
        links.append(OutcomeLink(label="View in Gravitre", href=result_url, kind="gravitre"))
    if external.startswith("http"):
        vendor = str(er.get("integration") or params.get("integration") or "vendor").title()
        links.append(OutcomeLink(label=f"View in {vendor}", href=external, kind="vendor"))
    # Surface every connector deep link collected at finalize (Apollo list, HubSpot list, …).
    step_refs = params.get("connector_output_refs") or params.get("step_results") or []
    if isinstance(step_refs, list):
        seen = {link.href for link in links}
        for ref in step_refs:
            if not isinstance(ref, dict):
                continue
            href = str(ref.get("external_url") or "").strip()
            if not href.startswith("http") or href in seen:
                continue
            label_vendor = str(ref.get("integration") or "vendor").title()
            step_label = str(ref.get("label") or ref.get("invoke_action") or label_vendor)
            links.append(
                OutcomeLink(
                    label=f"Open: {step_label}"[:80],
                    href=href,
                    kind="vendor",
                )
            )
            seen.add(href)
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
        integration=str(er.get("integration") or params.get("integration") or "") or None,
    )


def _verification(
    er: dict[str, Any],
    *,
    status: str,
    invoke_action: str | None = None,
    params: dict[str, Any] | None = None,
) -> VerificationSection | None:
    if str(status).lower() in {"failed", "error", "cancelled"}:
        return VerificationSection(
            verified=False,
            method="module_a_terminal_status",
            detail="Outcome terminated without successful verification.",
        )
    body = str(er.get("body") or "").strip()
    external = str(er.get("external_url") or "").strip()
    result_url = str(er.get("result_url") or "").strip()
    structured = er.get("structured") if isinstance(er.get("structured"), dict) else {}
    params = params if isinstance(params, dict) else {}
    from app.services.connector_outcome_effects import (
        classify_write_effect,
        has_effect_proof,
        is_mutating_action,
    )

    action = str(
        invoke_action or params.get("invoke_action") or params.get("invokeAction") or ""
    )
    # Phase 4 — degenerate batch: never claim verified; carry concrete finding.
    deg = (
        params.get("batch_degeneracy")
        if isinstance(params.get("batch_degeneracy"), dict)
        else structured.get("batch_degeneracy")
        if isinstance(structured.get("batch_degeneracy"), dict)
        else None
    )
    if str(status).lower() == "flagged_for_review" or (
        isinstance(deg, dict) and deg.get("flagged") is True
    ):
        from app.services.batch_degeneracy import (
            batch_degeneracy_next_actions,
            format_batch_degeneracy_finding,
        )

        finding = format_batch_degeneracy_finding(deg or {})
        return VerificationSection(
            verified=False,
            method="batch_degeneracy",
            detail=(
                "Phase 4 check failed: records look schema-valid but the batch is "
                "degenerate (identical or placeholder-dominated values)."
            ),
            review_state="flagged_for_review",
            check_failed="batch_degeneracy",
            finding=finding,
            next_actions=batch_degeneracy_next_actions(deg),
        )

    # Phase 3 — missing follow-up membership proof (distinct from Phase 4).
    pop = (
        params.get("population_verify")
        if isinstance(params.get("population_verify"), dict)
        else structured.get("population_verify")
        if isinstance(structured.get("population_verify"), dict)
        else None
    )
    if isinstance(pop, dict) and pop.get("verified") is False:
        detail_code = str(pop.get("detail") or "follow_up_unavailable_or_async").strip()
        finding = (
            f"Phase 3 follow-up proof missing ({detail_code}). "
            "The write was accepted but membership/completion was not confirmed."
        )
        return VerificationSection(
            verified=False,
            method="follow_up_proof",
            detail=(
                "Phase 3 check failed: mutating list/populate write lacks confirmed "
                "follow-up membership proof."
            ),
            review_state=None,
            check_failed="follow_up_proof",
            finding=finding,
            next_actions=[
                "Open the list in the source system and confirm contacts were added.",
                "Wait for vendor async settle, then re-check membership on the list.",
                "Retry the populate action if the list is still empty after settle.",
            ],
        )

    effect = str(
        params.get("outcome_effect")
        or structured.get("outcome_effect")
        or classify_write_effect(
            invoke_action=action or None,
            result_data=structured or None,
            success=str(status).lower() in {"completed", "partial_success"},
            metadata=params,
        )
        or ""
    ).strip().lower()
    already = (
        structured.get("already_existed") is True
        or effect == "already_existed"
        or body.lower().startswith("found existing")
    )
    if already and (body or external or result_url or str(status).lower() == "partial_success"):
        return VerificationSection(
            verified=True,
            method="module_a_idempotent_find",
            detail=(
                "Verified as an idempotent find (existing vendor record). "
                "No net-new create and no membership/enrichment side effect was proven."
            ),
        )
    if effect == "accepted_async" or (
        str(status).lower() == "partial_success" and effect == "accepted_async"
    ):
        return VerificationSection(
            verified=True,
            confidence="accepted_unproven",
            method="module_a_async_accepted",
            detail="Vendor accepted the write asynchronously; completion is not yet proven.",
            next_actions=[
                "Open the record in the source system to confirm it exists.",
                "Re-check shortly — the vendor may still be processing the write.",
            ],
        )
    if effect == "noop" or (
        str(status).lower() == "partial_success" and effect == "noop"
    ):
        return VerificationSection(
            verified=True,
            method="module_a_idempotent_find",
            detail="Verified as a no-op — vendor reported no net change.",
        )
    proven = has_effect_proof(structured, er)
    mutating = is_mutating_action(action)
    if mutating and (effect == "unknown" or not proven):
        # Do not claim module_a_verified_output for unproven creates.
        return VerificationSection(
            verified=False,
            method="module_a_effect_unproven",
            detail=(
                "Mutating action completed without durable entity proof "
                "(id / list_id / contact_id / vendor URL). Treated as unproven effect."
            ),
            check_failed="effect_unproven",
            finding=(
                "No durable vendor entity proof (id / list_id / contact_id / URL) "
                "was returned for this mutating action."
            ),
            next_actions=[
                "Open the run Evidence links and confirm whether a vendor record exists.",
                "Retry the action if the vendor record is missing.",
                "Do not treat this as a verified create until proof appears.",
            ],
        )
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
    from app.services.connector_output_refs import extract_step_output_ref

    steps: list[TimelineStep] = []
    for idx, row in enumerate(raw_steps):
        if not isinstance(row, dict):
            continue
        ref = extract_step_output_ref(row) or {}
        snap = row.get("output_snapshot") if isinstance(row.get("output_snapshot"), dict) else {}
        evidence = str(
            ref.get("external_url")
            or ref.get("result_url")
            or row.get("external_url")
            or row.get("url")
            or row.get("result_url")
            or snap.get("external_url")
            or snap.get("result_url")
            or ""
        ).strip() or None
        # Prefer vendor http links for "open completed work"; keep gravitre paths too.
        steps.append(
            TimelineStep(
                index=idx + 1,
                label=str(
                    ref.get("label")
                    or row.get("label")
                    or row.get("step_name")
                    or row.get("name")
                    or f"Step {idx + 1}"
                ),
                status=str(
                    row.get("status")
                    or ref.get("status")
                    or ("completed" if row.get("success") else "unknown")
                ),
                summary=str(
                    ref.get("summary")
                    or snap.get("summary")
                    or row.get("summary")
                    or row.get("error")
                    or row.get("body")
                    or ""
                )[:500]
                or None,
                evidence_url=evidence,
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
