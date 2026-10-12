"""Phase 8: account evidence proposes a Play; guards against repeat outreach and delegation loops."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.services.test_phase5_operational import _DB

ORG = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
ON = SimpleNamespace(
    account_play_proposals_enabled=True, work_object_proposals_enabled=True, account_health_enabled=True
)


def _health(**statuses: str) -> dict:
    from app.services.account_health import DEFINITIONS

    return {
        "entity": {"id": "e1", "name": "Acme"},
        "dimensions": [
            {
                "key": k,
                "label": DEFINITIONS[k]["label"],
                "definition": DEFINITIONS[k]["definition"],
                "status": statuses.get(k, "healthy"),
                "evidence": [f'"{k} quote"'],
                "coverage": {"observations": 6},
            }
            for k in DEFINITIONS
        ],
    }


def test_rules_group_dimensions_by_play():
    from app.services.account_play_triggers import matched_plays

    plays = matched_plays(_health(sentiment="at_risk", churn_risk_language="watch", contact_gap="at_risk"))
    assert sorted(plays) == ["client-risk-radar", "customer-rescue"]
    assert [d["key"] for d in plays["customer-rescue"]] == ["churn_risk_language", "sentiment"]
    assert matched_plays(_health(sentiment="watch", urgency="watch")) == {}


def test_proposal_carries_evidence_and_never_runs_anything():
    from app.services.account_play_triggers import propose_for_account

    db = _DB()
    out = propose_for_account(db, ON, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW)
    assert [o["play"] for o in out] == ["customer-rescue"] and out[0]["status"] == "proposed"
    (row,) = db.tables["work_objects"]
    assert row["status"] == "proposed" and row["business_entity_id"] == "e1"
    assert row["priority"] == "high"
    proposal = row["metadata"]["proposal"]
    assert proposal["play_key"] == "customer-rescue" and proposal["source"] == "account_health"
    assert proposal["evidence"][0]["evidence"] == ['"sentiment quote"']
    assert "without approval" in row["objective"]
    assert set(db.tables) == {"work_objects"}  # no runs, jobs or messages
    assert not [w for w in db.writes if w[0] == "rpc"]


def test_same_window_is_deduplicated():
    from app.services.account_play_triggers import propose_for_account

    db = _DB()
    propose_for_account(db, ON, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW)
    second = propose_for_account(db, ON, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW)
    # the first proposal is still open work for this account and Play
    assert second == [{"play": "customer-rescue", "skipped": "open_work"}]
    assert len(db.tables["work_objects"]) == 1


def test_cooldown_spans_the_window_boundary():
    from app.services.account_play_triggers import (
        COOLDOWN_DAYS,
        _key,
        _window,
        propose_for_account,
    )

    db = _DB()
    db.tables["work_objects"] = [
        {
            "id": "old",
            "org_id": ORG,
            "status": "archived",  # dismissed, so not open work
            "external_entity_type": "proposal",
            "external_entity_id": _key("customer-rescue", "e1", _window(NOW) - 1),
            "created_at": (NOW - timedelta(days=COOLDOWN_DAYS - 1)).isoformat(),
        }
    ]
    out = propose_for_account(db, ON, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW)
    assert out == [{"play": "customer-rescue", "skipped": "cooldown"}]
    db.tables["work_objects"][0]["created_at"] = (NOW - timedelta(days=COOLDOWN_DAYS + 1)).isoformat()
    out = propose_for_account(db, ON, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW)
    assert out[0]["status"] == "proposed"


def test_closed_work_from_the_play_does_not_block():
    from app.services.account_play_triggers import propose_for_account

    db = _DB()
    db.tables["work_objects"] = [
        {"id": "w", "org_id": ORG, "business_entity_id": "e1", "status": "completed",
         "metadata": {"proposal": {"play_key": "customer-rescue"}}},
    ]
    out = propose_for_account(db, ON, org_id=ORG, health=_health(support_friction="at_risk"), now=NOW)
    assert out[0]["status"] == "proposed"


@pytest.mark.parametrize("off", ["account_play_proposals_enabled", "work_object_proposals_enabled", "account_health_enabled"])
def test_every_flag_is_required(off):
    from app.services.account_play_triggers import propose_for_account

    settings = SimpleNamespace(**{**vars(ON), off: False})
    db = _DB()
    assert propose_for_account(db, settings, org_id=ORG, health=_health(sentiment="at_risk"), now=NOW) == []
    assert "work_objects" not in db.tables


def test_scheduler_proposes_only_when_enabled():
    from app.schedulers.entity_behavior_signals_scheduler import run_behavior_signals

    db = _DB()
    db.tables["entity_observations"] = [{"org_id": ORG, "observed_at": NOW.isoformat()}]
    calls = []
    import app.services.account_play_triggers as triggers

    original = triggers.run_account_play_proposals
    triggers.run_account_play_proposals = lambda *a, **k: calls.append(a[2]) or []
    try:
        run_behavior_signals(db, now=NOW)
        assert calls == []
        run_behavior_signals(db, now=NOW, settings=ON)
        assert calls == [ORG]
    finally:
        triggers.run_account_play_proposals = original


def test_delegation_cannot_loop_back_or_go_too_deep():
    from app.services.agent_delegation_strategy import (
        MAX_DELEGATION_DEPTH,
        DelegationLoopError,
        create_child_plan_for_delegation,
        delegation_chain,
    )
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

    root = ExecutionPlan(
        plan_id="root",
        summary="s",
        steps=[ExecutionStep(step_id="d", title="d", kind="agent_delegation")],
        source="test",
    )
    a = create_child_plan_for_delegation(root, parent_step_id="d", agent_id="a", objective="x")
    b = create_child_plan_for_delegation(a, parent_step_id="agent_a_primary", agent_id="b", objective="x")
    assert delegation_chain(b) == ["a", "b"]
    with pytest.raises(DelegationLoopError):
        create_child_plan_for_delegation(b, parent_step_id="agent_b_primary", agent_id="a", objective="x")
    plan = b
    for i in range(MAX_DELEGATION_DEPTH - 2):
        plan = create_child_plan_for_delegation(plan, parent_step_id="p", agent_id=f"c{i}", objective="x")
    with pytest.raises(DelegationLoopError):
        create_child_plan_for_delegation(plan, parent_step_id="p", agent_id="z", objective="x")
