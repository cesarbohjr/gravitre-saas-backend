"""Objective-first acceptance: one sentence to a governed, verifiable plan, for every department."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.outcome_packs.memory_store import MemoryStore
from app.services import objective_capability_composer as oc
from app.services.capability_availability import record_unavailable

ORG = "00000000-0000-4000-8000-0000000000a1"

CASES = [
    ("Help me generate 150 qualified leads per month.", {"hubspot", "apollo"}, "qualified_leads", 150.0, "month"),
    ("Grow organic clicks by 20% this quarter", {"google_search_console"}, "organic_clicks", None, "quarter"),
    ("Help us close $500k in won revenue per quarter", {"salesforce"}, "won_revenue", 500000.0, "quarter"),
    ("Reduce our MTTR to 4 hours", {"freshservice"}, "mttr", 240.0, "month"),
    ("Help me retain 95 customers per month", {"stripe", "hubspot"}, "customers_retained", 95.0, "month"),
]


def _plan(text, vendors, store=None):
    with patch("app.capabilities.registry.connected_vendors", return_value=vendors):
        return oc.plan_objective(store or MemoryStore(), ORG, text)


@pytest.mark.parametrize("text,vendors,metric,target,period", CASES)
def test_objective_sentence_becomes_verifiable_plan(text, vendors, metric, target, period):
    assert oc.looks_like_objective(text)
    brief = _plan(text, vendors)
    contract = brief["contract"]
    assert contract["metricKey"] == metric
    assert contract["target"]["value"] == target
    assert contract["target"]["period"] == period
    assert contract["verificationRecipe"] or metric in {"mttr"}
    # No verified evidence yet: baseline is unknown, never zero.
    assert contract["baseline"]["value"] is None
    assert brief["feasibility"]["verdict"] == "achievable_plan"
    assert brief["feasibility"]["targetIsNotAPromise"] is True
    steps = brief["plan"]["steps"]
    assert steps and all(s["status"] in {"ready", "degraded"} for s in steps)
    assert any(s["movesPrimary"] for s in steps)
    # Plain-language summary: no internal ids or tool names.
    assert "." not in "".join(w for w in brief["summary"].split() if w.count(".") > 1)
    assert "_" not in brief["summary"]


def test_not_an_objective():
    assert not oc.looks_like_objective("what is our MQL count?")
    assert not oc.looks_like_objective("thanks!")


def test_plan_limit_replans_to_alternative_provider():
    store = MemoryStore()
    vendors = {"hubspot", "apollo", "pdl"}
    with patch("app.capabilities.registry.connected_vendors", return_value=vendors):
        brief = oc.plan_objective(store, ORG, "Help me generate 150 qualified leads per month.")
        saved = oc.save_objective(store, ORG, brief, status="active")
        step = next(s for s in brief["plan"]["steps"] if "prospect.discovery" in s["capabilityVendors"])
        assert step["capabilityVendors"]["prospect.discovery"] == "apollo"
        record_unavailable(store, ORG, action="apollo.people.search", state="plan_limit", reason="plan limit")
        result = oc.replan_objective(store, ORG, saved["objectiveId"], reason="provider_unavailable")
    assert result["changed"] is True
    changed = next(c for c in result["changes"] if c["playKey"] == step["playKey"])
    assert changed["after"]["prospect.discovery"] != "apollo"
    progress = oc.objective_progress(store, ORG, saved["objectiveId"])
    assert [h["revision"] for h in progress["planHistory"]] == [2, 1]
    assert progress["current"] is None and progress["remaining"] is None


def test_missing_connector_is_a_constraint_not_a_promise():
    brief = _plan("Help me generate 150 qualified leads per month.", set())
    assert brief["feasibility"]["verdict"] == "blocked"
    assert any(c["kind"] == "connect" for c in brief["feasibility"]["constraints"])


def test_planner_composes_real_resources():
    brief = _plan("Help me generate 150 qualified leads per month.", {"hubspot", "apollo"})
    state = oc.capability_resources_for_planner(brief)
    assert state["objective_contract"]["required_capabilities"]
    assert any(r["resource_id"] == "connector:hubspot" for r in state["capability_resources"])
    from app.services.cognitive_planner import CognitivePlanner

    plan = CognitivePlanner().plan("Help me generate 150 qualified leads per month.", state, None, None)
    assert plan["capability_composition"]["ready"] is True


def test_execution_requests_follow_play_runtime_modes():
    steps = [{"playKey": "a", "name": "A", "capabilityVendors": {}}, {"playKey": "b", "name": "B", "capabilityVendors": {}},
             {"playKey": "c", "name": "C", "capabilityVendors": {"x": "y"}}]
    installs = {"b": {"id": "i-b", "operating_mode": "OBSERVE"}, "c": {"id": "i-c", "operating_mode": "ACT WITH APPROVAL"}}
    states = {r["playKey"]: r["state"] for r in oc.execution_requests(steps, installs, "obj")}
    assert states == {"a": "needs_setup", "b": "needs_action_mode", "c": "runnable"}
