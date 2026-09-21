"""3.0-H: entity id on ExecutionPlan; tenant isolation; no silent merge."""
from __future__ import annotations

from app.services.business_entity_fabric import (
    EntityBinding,
    EntityEvidence,
    join_provider_bindings,
)
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.gravitre_e2e_test_org import (
    ALPHA_ENTITY_ID,
    E2E_ORG_ID,
    seed_test_customer_alpha,
)
from app.services.conversation_write_guard import FORBIDDEN_OPERATOR_ORG_ID
from app.services.reasoning_evidence_pipeline import stamp_entity_on_execution_plan


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="plan-h",
        summary="why pipeline",
        steps=[
            ExecutionStep(
                step_id="e1",
                title="hubspot",
                kind="evidence",
                connector_id="hubspot",
            ),
            ExecutionStep(
                step_id="e2",
                title="qbo",
                kind="evidence",
                connector_id="quickbooks",
            ),
        ],
        source="test",
    )


def test_alpha_entity_id_survives_on_execution_plan() -> None:
    entity = seed_test_customer_alpha()
    plan = stamp_entity_on_execution_plan(
        _plan(),
        entity=entity,
        expected_org_id=E2E_ORG_ID,
        store_available=True,
    )
    assert entity.id == ALPHA_ENTITY_ID
    assert plan.entity_id == ALPHA_ENTITY_ID
    assert plan.entity_id != FORBIDDEN_OPERATOR_ORG_ID
    for step in plan.steps:
        if step.kind == "evidence":
            assert step.meta.get("entity_id") == ALPHA_ENTITY_ID
    roundtrip = ExecutionPlan.from_dict(plan.as_dict())
    assert roundtrip is not None
    assert roundtrip.entity_id == ALPHA_ENTITY_ID


def test_cross_org_entity_not_stamped_on_plan() -> None:
    entity = seed_test_customer_alpha()
    plan = stamp_entity_on_execution_plan(
        _plan(),
        entity=entity,
        expected_org_id="00000000-0000-4000-8000-000000000099",
        store_available=True,
    )
    assert plan.entity_id is None
    assert all(step.meta.get("entity_id") is None for step in plan.steps)


def test_join_refuses_foreign_org_binding() -> None:
    host = EntityEvidence(kind="host", value="alpha.test.gravitre.app", source="hubspot")
    left = EntityBinding(
        system="hubspot",
        resource_type="company",
        resource_id="hs-1",
        confidence=0.95,  # confidence-honesty-ok: unit join fixture
        evidence=(host,),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="organization",
        resource_id="zd-1",
        confidence=0.95,  # confidence-honesty-ok: unit join fixture
        evidence=(host,),
    )
    decision = join_provider_bindings(
        org_id=E2E_ORG_ID,
        display_name="Alpha",
        kind="company",
        left=left,
        right=right,
        left_org_id=E2E_ORG_ID,
        right_org_id=FORBIDDEN_OPERATOR_ORG_ID,
    )
    assert decision.status == "refused_cross_org"
    assert decision.entity is None
