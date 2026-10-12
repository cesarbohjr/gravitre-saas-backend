"""Phase 5: goals write path, goal links, proposals, Play signals, observation operands, feed."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "99999999-9999-4999-8999-999999999999"


class _DB(FakeSupabaseDB):
    """Fake that assigns ids on insert, like Postgres defaults."""

    def __init__(self) -> None:
        super().__init__()
        self._n = 0

    def table(self, name: str):
        q = super().table(name)
        original = q.insert

        def insert(payload, *a, **k):
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if "id" not in item:
                    self._n += 1
                    item["id"] = f"{name}-{self._n}"
            return original(payload, *a, **k)

        q.insert = insert  # type: ignore[method-assign]
        return q


# --------------------------------------------------------------------------- goals


def test_goal_create_matches_the_web_route_shape_and_validates():
    from app.services.goal_records import GoalValidationError, create_goal

    db = _DB()
    goal = create_goal(db, ORG, {"objective": "  Grow MQLs  ", "connectedSystems": ["hubspot"], "successMetrics": {"primary": "mqls"}})
    assert goal["objective"] == "Grow MQLs" and goal["status"] == "draft"
    assert goal["connectedSystems"] == ["hubspot"] and goal["successMetrics"] == {"primary": "mqls"}
    assert goal["orgId"] == ORG and "org_id" not in goal
    for bad in ({"objective": " "}, {"objective": "x", "status": "done"}, {"objective": "x", "connectedSystems": "hubspot"}):
        with pytest.raises(GoalValidationError):
            create_goal(db, ORG, bad)


def test_goal_update_is_org_scoped_partial_and_stamps_updated_at():
    from app.services.goal_records import GoalValidationError, update_goal

    db = _DB()
    db.tables["goals"] = [{"id": "g1", "org_id": ORG, "objective": "a", "status": "draft"}]
    with pytest.raises(GoalValidationError):
        update_goal(db, ORG, "g1", {})
    assert update_goal(db, OTHER, "g1", {"status": "active"}) is None
    goal = update_goal(db, ORG, "g1", {"status": "active"})
    assert goal["status"] == "active" and goal["objective"] == "a" and goal["updatedAt"]


def test_goal_routes_map_errors_and_scope_to_org(monkeypatch):
    from app.routers import goals as router

    db = _DB()
    monkeypatch.setattr(router, "shared_service_client", lambda *_a: db)
    settings = SimpleNamespace()
    created = router.create_goal_route({"objective": "Cut churn"}, {}, ORG, settings)["goal"]
    assert router.list_goals_route({}, ORG, settings)["goals"][0]["id"] == created["id"]
    assert router.list_goals_route({}, OTHER, settings)["goals"] == []
    with pytest.raises(HTTPException) as e:
        router.create_goal_route({"objective": ""}, {}, ORG, settings)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        router.get_goal_route(created["id"], {}, OTHER, settings)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        router.list_goals_route({}, None, settings)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        router.goal_linked_progress_route(created["id"], {}, ORG, settings)
    assert e.value.status_code == 404  # flag off


def test_goal_progress_counts_only_linked_work_and_ignores_proposals():
    from app.services.goal_records import goal_link_progress

    db = _DB()
    db.tables["work_objects"] = [
        {"id": "w1", "org_id": ORG, "goal_id": "g1", "status": "completed"},
        {"id": "w2", "org_id": ORG, "goal_id": "g1", "status": "in_progress"},
        {"id": "w3", "org_id": ORG, "goal_id": "g1", "status": "proposed"},
        {"id": "w4", "org_id": ORG, "goal_id": "g2", "status": "completed"},
    ]
    db.tables["agent_jobs"] = [
        {"id": "j1", "org_id": ORG, "goal_id": "g1", "status": "completed"},
        {"id": "j2", "org_id": ORG, "goal_id": "g1", "status": "cancelled"},
    ]
    p = goal_link_progress(db, ORG, "g1")
    assert p["completionPercentage"] == 67  # 2 of 3 counted
    assert p["proposedWork"] == 1 and p["linkedWork"]["total"] == 3
    assert goal_link_progress(db, ORG, "g-none")["completionPercentage"] is None


# --------------------------------------------------------------------------- agent job links


def test_agent_job_links_need_the_flag_and_same_org_rows():
    from app.routers.agent_jobs import EnqueueJobRequest, _validated_links

    db = _DB()
    db.tables["goals"] = [{"id": "g1", "org_id": ORG}]
    db.tables["work_objects"] = [{"id": "w1", "org_id": OTHER}]
    on = SimpleNamespace(goal_links_enabled=True)
    assert _validated_links(db, SimpleNamespace(), ORG, EnqueueJobRequest(task="t")) == (None, None)
    with pytest.raises(HTTPException) as e:
        _validated_links(db, SimpleNamespace(), ORG, EnqueueJobRequest(task="t", goalId="g1"))
    assert e.value.status_code == 422
    assert _validated_links(db, on, ORG, EnqueueJobRequest(task="t", goalId="g1")) == ("g1", None)
    with pytest.raises(HTTPException) as e:
        _validated_links(db, on, ORG, EnqueueJobRequest(task="t", workObjectId="w1"))
    assert e.value.status_code == 400


def test_create_job_writes_link_columns_only_when_given():
    from app.operators.agent_jobs import create_job

    db = _DB()
    create_job(db, ORG, payload={"task": "a"})
    create_job(db, ORG, payload={"task": "b"}, goal_id="g1", work_object_id="w1")
    first, second = db.tables["agent_jobs"]
    assert "goal_id" not in first and "work_object_id" not in first
    assert second["goal_id"] == "g1" and second["work_object_id"] == "w1"


# --------------------------------------------------------------------------- proposals


def test_proposals_are_off_by_default_need_evidence_and_dedupe():
    from app.services.work_object_proposals import ProposalError, propose_work_object

    db = _DB()
    kw = {"org_id": ORG, "title": "Call Acme", "dedupe_key": "acme:churn", "source": "observations",
          "evidence": [{"summary": "sentiment falling"}]}
    assert propose_work_object(db, SimpleNamespace(), **kw) == {"skipped": "disabled"}
    on = SimpleNamespace(work_object_proposals_enabled=True)
    with pytest.raises(ProposalError):
        propose_work_object(db, on, **{**kw, "evidence": []})
    first = propose_work_object(db, on, **kw, goal_id="g1")
    again = propose_work_object(db, on, **kw)
    assert first["status"] == "proposed" and not first["deduplicated"]
    assert again == {"id": first["id"], "status": "proposed", "deduplicated": True}
    row = db.tables["work_objects"][0]
    assert row["external_entity_type"] == "proposal" and row["goal_id"] == "g1"
    assert "business_entity_id" not in row


def test_proposals_stay_out_of_work_lists_until_accepted():
    from app.services.work_object_proposals import ProposalError, decide_proposal
    from app.services.work_object_service import (
        list_work_objects,
        summarize_work_object_coverage,
    )

    db = _DB()
    db.tables["work_objects"] = [
        {"id": "p1", "org_id": ORG, "status": "proposed", "title": "P", "object_type": "other", "metadata": {"proposal": {}}},
        {"id": "w1", "org_id": ORG, "status": "planned", "title": "W", "object_type": "other"},
    ]
    assert [w["id"] for w in list_work_objects(db, org_id=ORG)] == ["w1"]
    assert summarize_work_object_coverage(db, org_id=ORG)["count"] == 1
    assert decide_proposal(db, org_id=OTHER, work_object_id="p1", actor_id="u", accept=True) is None
    assert decide_proposal(db, org_id=ORG, work_object_id="p1", actor_id="u", accept=True, reason="yes")["status"] == "planned"
    assert db.tables["work_objects"][0]["metadata"]["proposal"]["decision"]["by"] == "u"
    with pytest.raises(ProposalError):
        decide_proposal(db, org_id=ORG, work_object_id="p1", actor_id="u", accept=False)


def test_executions_never_file_a_proposal():
    from app.services.work_object_service import _derive_work_status

    assert _derive_work_status("completed", current_status="identified", metadata={"work_object_status": "proposed"}) == "identified"


def test_proposal_routes_are_hidden_when_off():
    from app.routers.work_objects import ProposalDecisionRequest, accept_proposal_route

    with pytest.raises(HTTPException) as e:
        accept_proposal_route("00000000-0000-4000-8000-000000000001", ProposalDecisionRequest(), {"user_id": "u"}, ORG, SimpleNamespace())
    assert e.value.status_code == 404


# --------------------------------------------------------------------------- Play signals


def _play(signals: tuple[str, ...]):
    from app.plays.catalog import platform_play_templates

    base = next(p for p in platform_play_templates() if p.required_signals)
    return base.__class__(**{**base.__dict__, "required_signals": signals})


def test_signal_readiness_unchanged_without_evidence_and_partial_with_it():
    from app.plays.readiness import resolve_play_readiness

    play = _play(("workflow_completed", "observation.sentiment", "not_a_signal"))
    legacy = resolve_play_readiness(play, connected_vendors=set(), policy_authorized_actions=set(), metric_keys=set())
    # Legacy name check: workflow_completed is absent from the event taxonomy
    # and observation signals are unknown without evidence.
    assert [r["status"] for r in legacy.signals] == ["MISSING", "MISSING", "MISSING"]
    evaluated = resolve_play_readiness(
        play, connected_vendors=set(), policy_authorized_actions=set(), metric_keys=set(),
        observed_signals={"observation.sentiment"},
    )
    rows = {r["signal"]: r for r in evaluated.signals}
    assert rows["workflow_completed"]["status"] == "PARTIAL" and rows["workflow_completed"]["observed_recently"] is False
    assert rows["observation.sentiment"]["status"] == "AVAILABLE"
    assert any("no events for this org" in b for b in evaluated.blockers)


def test_org_observed_signals_maps_each_source_and_survives_a_failed_read():
    from app.plays.signal_evidence import org_observed_signals

    db = _DB()
    db.tables["intelligence_outcome_events"] = [{"org_id": ORG, "outcome_event": "prediction_generated"}]
    db.tables["workflow_runs"] = [{"org_id": ORG, "status": "completed"}, {"org_id": ORG, "status": "running"}]
    db.tables["entity_observations"] = [{"org_id": ORG, "dimension": "urgency"}]
    assert org_observed_signals(db, ORG) == {"prediction_generated", "workflow_completed", "observation.urgency"}
    broken = MagicMock()
    broken.table.side_effect = RuntimeError("missing table")
    assert org_observed_signals(broken, ORG) == set()


def test_plays_router_only_reads_signals_when_the_flag_is_on():
    from app.routers.plays import _observed_signals

    client = MagicMock()
    assert _observed_signals(SimpleNamespace(), client, ORG) is None
    client.table.assert_not_called()


# --------------------------------------------------------------------------- observation operands


def _obs_rows(direction: str, n: int = 6) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    start, end = (-0.6, 0.6) if direction == "rising" else (0.6, -0.6)
    return [
        {"dimension": "sentiment", "score": start + (end - start) * i / (n - 1), "status": "active",
         "observed_at": (now - timedelta(days=25 - 4 * i)).isoformat(), "source_system": "hubspot", "source_record_id": f"e{i}"}
        for i in range(n)
    ]


def test_recipes_get_observation_operands_only_when_they_reference_them():
    from app.marketplace.schemas import RecipeContributionConfig
    from app.outcome_packs.observation_operands import (
        observation_operands,
        recipe_uses_observations,
    )
    from app.outcome_packs.predicates import evaluate_predicate

    plain = SimpleNamespace(contributions=[RecipeContributionConfig(metric_key="m", when={"field": "current.stage", "op": "eq", "value": "won"})])
    uses = SimpleNamespace(contributions=[RecipeContributionConfig(
        metric_key="m", when={"all": [{"field": "current.stage", "op": "exists"}, {"field": "observations.sentiment.direction", "op": "eq", "value": "rising"}]}
    )])
    assert not recipe_uses_observations(plain) and recipe_uses_observations(uses)

    db = _DB()
    db.tables["org_business_entity_bindings"] = [{"org_id": ORG, "system": "hubspot", "resource_type": "company", "resource_id": "c1", "entity_id": "e1"}]
    db.tables["entity_observations"] = [{**r, "org_id": ORG, "entity_id": "e1"} for r in _obs_rows("rising")]
    ops = observation_operands(db, ORG, system="hubspot", record_type="company", record_id="c1")
    assert ops["sentiment"]["direction"] == "rising" and ops["urgency"]["direction"] == "insufficient_evidence"
    assert "latest_mean" not in ops["urgency"]
    record = {"current": {"stage": "won"}, "observations": ops}
    assert evaluate_predicate(uses.contributions[0].when, record)
    assert not evaluate_predicate({"field": "observations.urgency.latest_mean", "op": "gte", "value": 0}, record)
    assert observation_operands(db, ORG, system="hubspot", record_type="company", record_id="nope") == {}


# --------------------------------------------------------------------------- recommendation feed


def test_feed_items_carry_evidence_and_rank_on_shared_axes():
    from app.services.recommendation_feed import (
        items_from_accounts,
        items_from_business_signals,
        items_from_heuristic_cards,
        items_from_proposals,
    )

    sig = items_from_business_signals([{"id": "s1", "title": "Pipeline dip", "summary": "Down 20%", "estimated_impact": "high",
                                        "confidence": 0.8, "signal_type": "risk"}])[0]
    card = items_from_heuristic_cards([{"id": "c1", "title": "Connect Zendesk", "reason": "r", "evidence": {"usage": 3},
                                        "confidence": 0.4, "priority": 3, "href": "/connectors"}])[0]
    prop = items_from_proposals([{"id": "w1", "title": "Call Acme", "priority": "high",
                                  "metadata": {"proposal": {"source": "observations", "evidence": [{"summary": "sentiment falling"}]}}}])[0]
    assert sig["score"] > card["score"] and sig["advisoryOnly"] and card["actions"] == ["dismiss"]
    assert prop["actions"] == ["accept", "dismiss"] and prop["evidence"] == ["sentiment falling"]
    now = datetime.now(UTC)
    obs = [{**r, "entity_id": "e1", "evidence_quote": "q"} for r in _obs_rows("falling")]
    accounts = items_from_accounts(
        {"e1": "Acme"},
        obs,
        [{"entity_id": "e1", "signal": "contact_volume_change", "value": 3.0},
         {"entity_id": "e1", "signal": "contact_gap_days", "value": 4},
         {"entity_id": "e-unknown", "signal": "contact_gap_days", "value": 90}],
        now=now,
    )
    titles = [a["title"] for a in accounts]
    assert "Acme: sentiment is falling" in titles and "Acme: contact volume is 3.0x usual" in titles
    assert len(accounts) == 2  # small gap and unnamed entity left out
    assert all(a["evidence"] for a in accounts)


def test_feed_reports_each_source_and_keeps_going_when_one_fails():
    from app.services.recommendation_feed import build_feed

    engine = MagicMock()
    engine.collect_signals = AsyncMock(side_effect=RuntimeError("down"))
    with patch("app.services.business_signals_engine.get_business_signals_engine", return_value=engine), patch(
        "app.services.recommendation_heuristics_service.load_heuristic_signals",
        return_value={"connected_connectors": [], "usage_by_connector": {}, "installed_packs": [], "lookback_days": 30},
    ):
        out = asyncio.run(build_feed(_DB(), SimpleNamespace(), org_id=ORG, user_id=None))
    assert out["sources"] == {"business_signals": "error", "heuristic_cards": "ok", "proposals": "off", "accounts": "off"}
    assert all(i["advisoryOnly"] for i in out["items"])


def test_feed_route_is_hidden_when_off():
    from app.routers.recommendation_feed import recommendation_feed

    with pytest.raises(HTTPException) as e:
        asyncio.run(recommendation_feed({"user_id": "u"}, ORG, SimpleNamespace()))
    assert e.value.status_code == 404
