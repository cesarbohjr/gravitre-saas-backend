"""3.0-F why-pipeline golden: labels, join-when-store, parallel safe READs."""
from __future__ import annotations

import pytest

from app.services.business_entity_fabric import (
    BusinessEntity,
    EntityBinding,
    EntityEvidence,
    join_provider_bindings,
)
from app.services.cognitive_execution_engine import execute_read_steps_parallel
from app.services.execution_plan_service import ExecutionStep, reconcile_execution_plan
from app.services.multi_source_diagnostic import conclude_diagnostic
from app.services.reasoning_evidence_pipeline import (
    allow_speculative_read,
    apply_join_and_labels_to_plan,
    label_claim,
    parallel_safe_steps,
    plan_entity_join_for_reads,
)


def test_claim_labels():
    assert label_claim(live_observation=True) == "FACT"
    assert label_claim(live_observation=True, causal=True) == "INFERENCE"
    assert label_claim(hypothesized=True) == "HYPOTHESIS"
    assert label_claim(recommended_action=True) == "RECOMMENDATION"
    assert label_claim(insufficient_evidence=True) == "FACT"


def test_why_pipeline_golden_labels_and_parallel_group():
    plan = reconcile_execution_plan(
        message="Why did our pipeline fall this week?",
        task_state={},
        connected_integrations=["hubspot", "google_analytics"],
    )
    assert plan.source == "multi_source_diagnostic"
    kinds = [s.kind for s in plan.steps]
    assert "hypothesis" in kinds
    assert "evidence" in kinds
    hyp = next(s for s in plan.steps if s.kind == "hypothesis")
    assert hyp.meta.get("claim_label") == "HYPOTHESIS"
    evidence = [s for s in plan.steps if s.kind == "evidence"]
    assert evidence
    assert all(s.meta.get("parallel_group") == "independent_safe_reads" for s in evidence)
    assert all(s.kind != "write" for s in parallel_safe_steps(plan))
    verdict = conclude_diagnostic(plan, [])
    assert verdict["sufficient"] is False
    assert verdict["labels"][0]["label"] == "FACT"
    assert "guess" in verdict["message"].lower()


def test_join_only_when_entity_store_has_bindings():
    skipped = plan_entity_join_for_reads(
        entity=None,
        store_available=False,
        read_vendors=["google_analytics", "google_search_console"],
    )
    assert skipped["join"] is False
    assert skipped["reason"] == "entity_store_missing"

    empty = plan_entity_join_for_reads(
        entity=None,
        store_available=True,
        read_vendors=["google_analytics", "google_search_console"],
    )
    assert empty["join"] is False
    assert empty["reason"] == "no_accepted_entity"

    host = EntityEvidence(kind="host", value="acme.com", source="identity")
    entity = BusinessEntity(
        id="ent-1",
        org_id="org-1",
        display_name="Acme site",
        kind="website",
        bindings=(
            EntityBinding("google_analytics", "property", "123", 0.9, (host,)),
            EntityBinding("google_search_console", "site", "https://acme.com", 0.9, (host,)),
        ),
        evidence=(host,),
        confidence=0.9,
    )
    joined = plan_entity_join_for_reads(
        entity=entity,
        store_available=True,
        read_vendors=["google_analytics", "google_search_console"],
    )
    assert joined["join"] is True
    assert joined["entity_id"] == "ent-1"
    plan = reconcile_execution_plan(
        message="Why did our pipeline fall this week?",
        task_state={},
        connected_integrations=["hubspot", "google_analytics"],
    )
    stamped = apply_join_and_labels_to_plan(plan, join=joined)
    assert stamped.plan_id == plan.plan_id
    reads = [s for s in stamped.steps if s.kind == "evidence"]
    assert all(s.meta.get("parallel_group") == "joined_entity" for s in reads)


def test_person_join_refuses_fuzzy_names():
    left = EntityBinding(
        "hubspot",
        "contact",
        "1",
        0.99,
        (EntityEvidence("name", "Sarah", "crm"),),
    )
    right = EntityBinding(
        "salesforce",
        "contact",
        "2",
        0.99,
        (EntityEvidence("name", "Sarah Smith", "crm"),),
    )
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Sarah",
        kind="person",
        left=left,
        right=right,
    )
    assert decision.status == "refused_ambiguous"
    person = BusinessEntity(
        id="p1",
        org_id="org-1",
        display_name="Sarah",
        kind="person",
        bindings=(left, right),
        confidence=0.99,
    )
    plan = plan_entity_join_for_reads(
        entity=person,
        store_available=True,
        read_vendors=["hubspot", "salesforce"],
    )
    assert plan["join"] is False
    assert "sta312" in plan["reason"]


def test_never_speculative_write():
    assert (
        allow_speculative_read(
            step_kind="write",
            confidence=1.0,
            cheap=True,
            cancellable=True,
            privacy_escalation=False,
        )
        is False
    )
    assert (
        allow_speculative_read(
            step_kind="read",
            confidence=0.9,
            cheap=True,
            cancellable=True,
            privacy_escalation=False,
        )
        is True
    )
    assert (
        allow_speculative_read(
            step_kind="read",
            confidence=0.9,
            cheap=True,
            cancellable=True,
            privacy_escalation=True,
        )
        is False
    )


@pytest.mark.asyncio
async def test_parallel_engine_runs_evidence_not_writes():
    from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan

    plan = ExecutionPlan(
        plan_id="p-par",
        summary="diag",
        steps=[
            ExecutionStep(step_id="h1", title="h", kind="hypothesis"),
            ExecutionStep(step_id="e1", title="hubspot", kind="evidence", connector_id="hubspot"),
            ExecutionStep(step_id="e2", title="ga4", kind="evidence", connector_id="google_analytics"),
            ExecutionStep(step_id="w1", title="create", kind="write", connector_id="hubspot"),
        ],
        source="test",
        execution_strategy="PARALLEL",
    )

    async def handler(step: ExecutionStep, _ctx: dict) -> ExecutionObservation:
        return ExecutionObservation(
            step_id=step.step_id,
            connector_id=str(step.connector_id or ""),
            success=True,
            summary=step.step_id,
        )

    obs = await execute_read_steps_parallel(plan, context={}, handler=handler)
    ids = {o.step_id for o in obs}
    assert ids == {"e1", "e2"}
    assert "w1" not in ids
    assert "h1" not in ids
