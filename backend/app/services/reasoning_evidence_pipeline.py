"""3.0-F evidence reasoning — labels, join-when-store, parallel safe READs.

EXTEND E5 / 2.0-G diagnostics. Joins only when the BusinessEntity store has
accepted bindings. STA-312: no fuzzy person-name merge. Never speculative WRITE.
"""
from __future__ import annotations

from typing import Any, Literal

from app.services.business_entity_fabric import (
    JOIN_CONFIDENCE_THRESHOLD,
    BusinessEntity,
)
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

EvidenceLabel = Literal["FACT", "INFERENCE", "HYPOTHESIS", "RECOMMENDATION"]

SAFE_PARALLEL_KINDS = frozenset({"read", "evidence"})
WRITE_KINDS = frozenset({"write"})


def label_claim(
    *,
    live_observation: bool = False,
    causal: bool = False,
    recommended_action: bool = False,
    hypothesized: bool = False,
    insufficient_evidence: bool = False,
) -> EvidenceLabel:
    if recommended_action:
        return "RECOMMENDATION"
    if hypothesized and not live_observation:
        return "HYPOTHESIS"
    if causal and live_observation:
        return "INFERENCE"
    if insufficient_evidence:
        return "FACT"
    if live_observation and not causal:
        return "FACT"
    if causal:
        return "INFERENCE"
    return "HYPOTHESIS"


def allow_speculative_read(
    *,
    step_kind: str,
    confidence: float,
    cheap: bool,
    cancellable: bool,
    privacy_escalation: bool,
) -> bool:
    """Speculative READ only if high confidence, cheap, cancellable, no privacy jump."""
    kind = str(step_kind or "").strip().lower()
    if kind in WRITE_KINDS or kind == "write":
        return False
    if privacy_escalation:
        return False
    if not cheap or not cancellable:
        return False
    return float(confidence) >= JOIN_CONFIDENCE_THRESHOLD


def parallel_safe_steps(plan: ExecutionPlan) -> list[ExecutionStep]:
    """Independent evidence/read steps. WRITEs never included."""
    out: list[ExecutionStep] = []
    for step in plan.steps:
        if step.kind in WRITE_KINDS:
            continue
        if step.kind not in SAFE_PARALLEL_KINDS:
            continue
        if step.status not in {"pending", "running"}:
            continue
        out.append(step)
    return out


def plan_entity_join_for_reads(
    *,
    entity: BusinessEntity | None,
    store_available: bool,
    read_vendors: list[str] | None = None,
) -> dict[str, Any]:
    """Join planner: skip silently merging when the entity store is empty."""
    vendors = [str(v).strip().lower() for v in (read_vendors or []) if str(v).strip()]
    if not store_available:
        return {
            "join": False,
            "reason": "entity_store_missing",
            "parallel": True,
            "entity_id": None,
            "systems": [],
        }
    if entity is None:
        return {
            "join": False,
            "reason": "no_accepted_entity",
            "parallel": True,
            "entity_id": None,
            "systems": [],
        }
    if entity.kind == "person":
        return {
            "join": False,
            "reason": "person_join_deferred_sta312",
            "parallel": True,
            "entity_id": entity.id,
            "systems": [],
        }
    bound = {str(b.system).strip().lower() for b in entity.bindings}
    overlap = [v for v in vendors if v in bound] if vendors else sorted(bound)
    if len(set(overlap)) < 2:
        return {
            "join": False,
            "reason": "insufficient_bindings",
            "parallel": True,
            "entity_id": entity.id,
            "systems": overlap,
        }
    return {
        "join": True,
        "reason": "accepted_entity_bindings",
        "parallel": True,
        "entity_id": entity.id,
        "systems": overlap,
    }


def apply_join_and_labels_to_plan(
    plan: ExecutionPlan,
    *,
    join: dict[str, Any] | None = None,
) -> ExecutionPlan:
    """Stamp parallel_group + claim labels on E5 steps. Same plan_id."""
    decision = join if isinstance(join, dict) else plan_entity_join_for_reads(
        entity=None,
        store_available=False,
        read_vendors=[str(s.connector_id or "") for s in plan.steps],
    )
    group = "joined_entity" if decision.get("join") else "independent_safe_reads"
    updated: list[ExecutionStep] = []
    for step in plan.steps:
        meta = dict(step.meta)
        if step.kind in SAFE_PARALLEL_KINDS:
            meta["parallel_group"] = group
            meta["join_reason"] = decision.get("reason")
            if decision.get("entity_id"):
                meta["entity_id"] = decision.get("entity_id")
            meta["claim_label"] = "FACT"
        elif step.kind == "hypothesis":
            meta["claim_label"] = "HYPOTHESIS"
        elif step.kind == "compose":
            meta["claim_label"] = "INFERENCE"
        updated.append(
            ExecutionStep(
                step_id=step.step_id,
                title=step.title,
                kind=step.kind,
                connector_id=step.connector_id,
                capability_id=step.capability_id,
                action_key=step.action_key,
                status=step.status,
                meta=meta,
            )
        )
    plan.steps = updated
    stamped = decision.get("entity_id")
    plan.entity_id = str(stamped) if stamped else None
    if decision.get("join"):
        plan.execution_strategy = "PARALLEL"
    return plan


def stamp_entity_on_execution_plan(
    plan: ExecutionPlan,
    *,
    entity: BusinessEntity | None,
    expected_org_id: str,
    store_available: bool = True,
) -> ExecutionPlan:
    """3.0-H: BusinessEntity id survives on the E5 plan for this tenant only.

    Cross-org entities are refused (no silent merge). STA-312: person joins
    stay deferred in ``plan_entity_join_for_reads``.
    """
    if entity is not None and str(entity.org_id) != str(expected_org_id):
        return apply_join_and_labels_to_plan(
            plan,
            join={
                "join": False,
                "reason": "refused_cross_org",
                "parallel": True,
                "entity_id": None,
                "systems": [],
            },
        )
    vendors = [
        str(step.connector_id or "").strip().lower()
        for step in plan.steps
        if str(step.connector_id or "").strip()
    ]
    decision = plan_entity_join_for_reads(
        entity=entity,
        store_available=store_available,
        read_vendors=vendors,
    )
    return apply_join_and_labels_to_plan(plan, join=decision)
