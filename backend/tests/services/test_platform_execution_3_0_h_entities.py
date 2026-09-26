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


def test_listing_intent_matches_natural_language_hubspot_deals() -> None:
    from app.services.listing_f2_read_turn import listing_f2_intent

    intent = listing_f2_intent("List all HubSpot deals")
    assert intent is not None
    assert intent.provider == "hubspot"
    assert intent.search_tool == "hubspot.deals.search"
    assert intent.list_tool == "hubspot.deals.list"


def test_listing_intent_matches_hubspot_contact_count() -> None:
    from app.services.listing_f2_read_turn import listing_f2_intent, match_listing_f2_intent

    prompt = (
        "How many HubSpot contacts are in this isolated test account? "
        "Read only. Do not create or update anything."
    )
    intent = listing_f2_intent(prompt)
    assert intent is not None
    assert intent.search_tool == "hubspot.contacts.search"
    assert intent.count_query is True
    assert match_listing_f2_intent("Count HubSpot contacts") is True
    assert listing_f2_intent("Did that contact already get created?") is None
    assert listing_f2_intent("Create a HubSpot contact named Probe") is None
    from app.services.canonical_cognitive_resolution import should_skip_unified_live_for_compiled_read

    assert should_skip_unified_live_for_compiled_read(prompt, {}, ["hubspot"]) is True


def test_listing_disconnected_hubspot_does_not_fall_through() -> None:
    from app.services.listing_f2_read_turn import try_listing_f2_read_turn

    turn = try_listing_f2_read_turn(
        message="Count HubSpot contacts",
        org_id="org",
        client=None,
        settings=None,
        connected_integrations=[],
        task_state={},
    )
    assert turn is not None
    assert turn["stop_pipeline"] is True
    assert turn["workflow_status"] == "blocked"
    assert turn["writes_started"] is False


def test_listing_contact_count_binds_table_artifact() -> None:
    from unittest.mock import MagicMock, patch

    from app.services.listing_f2_read_turn import try_listing_f2_read_turn
    from app.services.tool_types import NormalizedResult

    invoked = NormalizedResult(
        success=True,
        action="hubspot.contacts.search",
        connector_id="hubspot",
        data={"total": 57, "results": [{"id": "skip-me"}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = MagicMock(observation_id="obs-count-1", success=True)
    with patch(
        "app.services.listing_f2_read_turn.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ) as mock_invoke:
        turn = try_listing_f2_read_turn(
            message="How many HubSpot contacts are in this account?",
            org_id="org",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
        )
    assert turn is not None
    assert turn["writes_started"] is False
    assert turn["execution_path"] == "listing_f2_read"
    assert turn["message"] == "This HubSpot account has 57 contacts."
    arts = turn["task_state"]["work_artifacts"]
    assert arts[-1]["kind"] == "table"
    assert arts[-1]["metadata"]["exportable"] is True
    assert "57" in str(arts[-1]["metadata"]["code"])
    assert "skip-me" not in str(arts[-1]["metadata"]["code"])
    rows = turn["task_state"]["execution_observations"][-1]["structured"]["rows"]
    assert rows == [
        {"system": "HubSpot", "object": "contacts", "count": 57, "source": "hubspot.contacts.search"}
    ]
    assert mock_invoke.call_args.kwargs["action_key"] == "hubspot.contacts.search"


def test_listing_bound_artifact_resume_does_not_reinvoke() -> None:
    from unittest.mock import patch

    from app.services.listing_f2_read_turn import try_listing_f2_read_turn

    state = {
        "execution_plan": {
            "plan_id": "plan-resume-1",
            "terminal_status": "completed",
            "source": "listing_f2_read",
            "steps": [],
        },
        "durable_deliverable": {"diagnosis": "This HubSpot account has 57 contacts."},
        "work_artifacts": [
            {
                "artifact_id": "report:plan-resume-1",
                "kind": "table",
                "title": "HubSpot contacts",
                "preview": "This HubSpot account has 57 contacts.",
                "metadata": {
                    "plan_id": "plan-resume-1",
                    "outcome": "completed",
                    "observation_ids": ["obs-count-1"],
                    "code": "Outcome: completed\nThis HubSpot account has 57 contacts.",
                    "exportable": True,
                },
            }
        ],
    }
    with patch("app.services.listing_f2_read_turn.invoke_sealed_f1_read") as mock_invoke:
        turn = try_listing_f2_read_turn(
            message="Show me that table",
            org_id="org",
            client=object(),
            settings=None,
            connected_integrations=["hubspot"],
            task_state=state,
        )
    mock_invoke.assert_not_called()
    assert turn is not None
    assert turn["execution_path"] == "listing_f2_read_resume"
    assert turn["provider_reinvoked"] is False
    assert turn["writes_started"] is False
    assert "57 contacts" in turn["message"]
    assert turn["execution_result"]["entity_id"] == "plan-resume-1"


def test_entity_join_intent_is_not_live_provider_claim() -> None:
    from app.services.entity_join_answer_turn import entity_join_intent

    intent = entity_join_intent("What do we know about Alpha across HubSpot, QuickBooks, and Zendesk?")
    assert intent is not None
    assert intent.display_name == "Alpha"


class _Table:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def select(self, *_a: object, **_k: object) -> "_Table":
        return self

    def eq(self, *_a: object, **_k: object) -> "_Table":
        return self

    def limit(self, *_a: object, **_k: object) -> "_Table":
        return self

    def execute(self) -> object:
        return type("R", (), {"data": self._rows})()


class _Store:
    def __init__(self, entities: list[dict], bindings: list[dict]) -> None:
        self._entities = entities
        self._bindings = bindings

    def table(self, name: str) -> _Table:
        if name == "org_business_entities":
            return _Table(self._entities)
        return _Table(self._bindings)


def test_store_answer_discloses_disconnected_live_sources() -> None:
    from app.services.entity_join_answer_turn import try_cross_system_entity_turn

    client = _Store(
        [
            {
                "id": "ent-1",
                "org_id": E2E_ORG_ID,
                "canonical_key": ALPHA_ENTITY_ID,
                "display_name": "Alpha",
                "kind": "company",
                "confidence": 0.95,
                "evidence": [{"kind": "host", "value": "alpha.test.gravitre.app", "source": "hubspot"}],
            }
        ],
        [
            {
                "entity_id": "ent-1",
                "system": "hubspot",
                "resource_type": "company",
                "resource_id": "hs-alpha-test",
                "confidence": 0.95,
                "evidence": [],
            },
            {
                "entity_id": "ent-1",
                "system": "quickbooks",
                "resource_type": "customer",
                "resource_id": "qbo-alpha-test",
                "confidence": 0.95,
                "evidence": [],
            },
        ],
    )
    turn = try_cross_system_entity_turn(
        message="What do we know about Alpha across HubSpot, QuickBooks, and Zendesk?",
        org_id=E2E_ORG_ID,
        client=client,
        connected_integrations=["hubspot"],
    )
    assert turn is not None
    assert turn["join"] is True
    assert turn["entity_id"] == ALPHA_ENTITY_ID
    assert "not a live multi-provider census" in str(turn["message"]).lower()
    assert turn["writes_started"] is False
    assert turn["missing_live_sources"]


def test_ambiguous_display_name_is_not_joined() -> None:
    from app.services.entity_join_answer_turn import try_cross_system_entity_turn

    turn = try_cross_system_entity_turn(
        message="What do we know about Beta across HubSpot and QuickBooks?",
        org_id=E2E_ORG_ID,
        client=_Store(
            [
                {
                    "id": "ent-1",
                    "org_id": E2E_ORG_ID,
                    "canonical_key": ALPHA_ENTITY_ID,
                    "display_name": "Alpha",
                    "kind": "company",
                    "confidence": 0.95,
                    "evidence": [],
                }
            ],
            [
                {
                    "entity_id": "ent-1",
                    "system": "hubspot",
                    "resource_type": "company",
                    "resource_id": "hs-alpha-test",
                    "confidence": 0.95,
                    "evidence": [],
                },
                {
                    "entity_id": "ent-1",
                    "system": "quickbooks",
                    "resource_type": "customer",
                    "resource_id": "qbo-alpha-test",
                    "confidence": 0.95,
                    "evidence": [],
                },
            ],
        ),
        connected_integrations=["hubspot"],
    )
    assert turn is not None
    assert turn["join"] is False
    assert "similar display name" in str(turn["message"]).lower()


def test_compiled_read_runs_after_ledger_before_cognitive_kernel() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "app" / "operators" / "agent_intelligence.py"
    text = src.read_text(encoding="utf-8")
    ledger = text.find('_mark("parameter_ledger")')
    after = text[ledger:]
    compiled = after.find("try_compiled_operational_read_turn")
    kernel = after.find("run_pre_act")
    assert ledger >= 0
    assert 0 <= compiled < kernel
    assert "try_computer_browser_interact_turn" in after
    first_interact = text.find("try_computer_browser_interact_turn")
    shortcut = text.find('gateway.action == "shortcut"')
    assert 0 <= first_interact < shortcut
    assert "if spoken_lite_path or _compiled_read_ingress:" in text
    assert '"listing_f2_read"' in text
    assert '"computer_browser_read"' in text


def test_contact_count_compiled_ingress_skips_understand_class() -> None:
    from app.services.canonical_cognitive_resolution import should_skip_unified_live_for_compiled_read
    from app.services.listing_f2_read_turn import listing_f2_intent
    from app.services.operator_task_intent import looks_like_operator_task

    prompt = (
        "How many HubSpot contacts are in this isolated test account? "
        "Read only. Do not create or update anything."
    )
    assert listing_f2_intent(prompt) is not None
    assert looks_like_operator_task(prompt) is False
    assert should_skip_unified_live_for_compiled_read(prompt, {}, ["hubspot"]) is True
