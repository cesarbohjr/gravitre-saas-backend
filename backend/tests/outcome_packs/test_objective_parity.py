"""Objective-first acceptance on one engine: capability states, corrections and text/voice parity.

These run the real objective composer, capability availability, cognitive
planner and cognitive turn kernel against the in-memory PostgREST store. Only
the connector inventory and the web-research provider switch are patched, so
the assertions describe what production planning would decide for the same
tenant state.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.outcome_packs.memory_store import MemoryStore
from app.services import capability_availability as ca
from app.services import objective_capability_composer as oc
from app.services.tool_types import NormalizedResult

ORG = "00000000-0000-4000-8000-0000000000c3"
LEADS = "Help me generate 150 qualified leads per month."
CORRECTION = "Actually, make that Canadian MSPs with 20–100 employees."


def _tenant(vendors: set[str], *, web: bool = True) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("app.capabilities.registry.connected_vendors", return_value=vendors))
    stack.enter_context(patch("app.services.capability_availability.web_research_available", return_value=web))
    return stack


# --------------------------------------------------------------------------- capability universe


def test_disconnected_supported_providers_inform_the_plan_but_never_execute():
    """HubSpot connected; Apollo and Clay supported but disconnected; web research executable."""
    with _tenant({"hubspot"}):
        brief = oc.plan_objective(MemoryStore(), ORG, LEADS)
    ledger = brief["plan"]["capabilityLedger"]
    discovery = ledger["prospect.discovery"]
    assert discovery["status"] == "research"
    assert discovery["selected"] == "gravitre"
    assert discovery["states"]["apollo"] == "not_connected"
    assert discovery["states"]["clay"] == "not_connected"
    assert discovery["states"]["gravitre"] == "executable"
    assert {"apollo", "clay"} <= set(discovery["improvements"])
    # HubSpot stays the source of record for the CRM write.
    assert ledger["crm.contact.create"]["selected"] == "hubspot"
    # No step may name a disconnected provider as its executor.
    for step in brief["plan"]["steps"]:
        assert not {"apollo", "clay"} & set(step["capabilityVendors"].values())
    assert "connecting Apollo" in brief["summary"] and "Optional" in brief["summary"]

    calls: list[str] = []

    def invoke(ctx, action, params):  # pragma: no cover - must never be called
        calls.append(action)
        return NormalizedResult(success=True, action=action, data={})

    ctx = SimpleNamespace(client=MemoryStore(), org_id=ORG, settings=object())
    with patch("app.services.capability_availability.run_web_research") as research:
        research.return_value = NormalizedResult(success=True, action=ca.WEB_RESEARCH_ACTION, data={"results": []})
        with patch("app.services.capability_availability.web_research_available", return_value=True):
            result = ca.invoke_capability_with_fallback(
                ctx, "capability.prospect.discovery", {"_connected_integrations": ["hubspot"]}, invoke=invoke
            )
    assert result.action == ca.WEB_RESEARCH_ACTION
    assert calls == []


def test_entitlement_is_not_authentication_and_is_replanned_without_retrying():
    """Apollo connected and authenticated, but the plan refuses people search; web research is available."""
    store = MemoryStore()
    ca.record_unavailable(store, ORG, action="apollo.people.search", state="plan_limit", reason="402 upgrade your plan")
    with _tenant({"hubspot", "apollo"}):
        brief = oc.plan_objective(store, ORG, LEADS)
    discovery = brief["plan"]["capabilityLedger"]["prospect.discovery"]
    assert discovery["states"]["apollo"] == "not_entitled"  # not "not_authorized", not "not_connected"
    assert discovery["selected"] != "apollo"
    assert "apollo:plan_limit" in discovery["refused"]
    # Entitlement is per action: Apollo enrichment is still the chosen enricher.
    assert brief["plan"]["capabilityLedger"]["prospect.enrichment"]["selected"] == "apollo"
    assert "Apollo is connected, but its current plan does not include this action" in brief["summary"]

    # Authentication failure is a different rung.
    store2 = MemoryStore()
    ca.record_unavailable(store2, ORG, action="apollo.people.search", state="auth_expired", reason="401")
    states = ca.provider_states(
        "prospect.discovery", connected=["apollo"], blocks=ca.load_blocks(store2, ORG), web_research=True
    )
    assert next(p for p in states if p["vendor"] == "apollo")["state"] == "not_authorized"


def test_runtime_entitlement_refusal_falls_back_in_turn_and_never_retries():
    store = MemoryStore()
    calls: list[str] = []

    def invoke(ctx, action, params):
        calls.append(action)
        return NormalizedResult(success=False, action=action, error_message="402 Payment Required: upgrade your plan")

    ctx = SimpleNamespace(client=store, org_id=ORG, settings=object())
    with patch("app.services.capability_availability.web_research_available", return_value=True), patch(
        "app.services.capability_availability.run_web_research",
        return_value=NormalizedResult(success=True, action=ca.WEB_RESEARCH_ACTION, data={"results": []}),
    ):
        # Reads fall back in the same turn without an explicit opt-in.
        first = ca.invoke_capability_with_fallback(
            ctx, "capability.prospect.discovery", {"_connected_integrations": ["hubspot", "apollo"]}, invoke=invoke
        )
        second = ca.invoke_capability_with_fallback(
            ctx, "capability.prospect.discovery", {"_connected_integrations": ["hubspot", "apollo"]}, invoke=invoke
        )
    assert first.success and first.action == ca.WEB_RESEARCH_ACTION
    assert first.data["capability_fallback"]["skipped"][0]["state"] == "plan_limit"
    assert second.success
    assert calls == ["apollo.people.search"]  # tried once, never retried


def test_writes_still_need_explicit_fallback_opt_in():
    with pytest.raises(Exception) as exc:
        ca.invoke_capability_with_fallback(
            SimpleNamespace(client=MemoryStore(), org_id=ORG, settings=None),
            "capability.crm.deal.create",
            {"_connected_integrations": ["hubspot", "salesforce"]},
            invoke=lambda *a: None,
        )
    assert getattr(exc.value, "code", "") == "CAPABILITY_AMBIGUOUS"


# --------------------------------------------------------------------------- objective corrections


def test_constraints_never_become_the_target():
    parsed = oc.parse_objective("Help me generate 150 qualified leads per month from Canadian MSPs with 20-100 employees")
    assert parsed["target"] == 150.0
    assert parsed["constraints"] == {
        "geography": ["Canada"],
        "employees": {"min": 20, "max": 100},
        "segment": "MSPs",
    }


def test_correction_revises_only_what_it_names():
    store = MemoryStore()
    with _tenant({"hubspot", "apollo"}):
        first = oc.plan_objective(store, ORG, LEADS)
        active = oc.objective_state(first)
        assert oc.is_objective_revision(CORRECTION, active)
        revised = oc.revise_objective(store, ORG, active, CORRECTION)
    before, after = first["contract"], revised["contract"]
    assert after["constraints"] == {"geography": ["Canada"], "employees": {"min": 20, "max": 100}, "segment": "MSPs"}
    for key in ("metricKey", "definition", "verificationRecipe", "sourceSystem", "direction", "successMetrics"):
        assert after[key] == before[key], key
    assert after["target"]["value"] == 150.0 and after["target"]["period"] == "month"
    assert [s["playKey"] for s in revised["plan"]["steps"]] == [s["playKey"] for s in first["plan"]["steps"]]
    assert revised["plan"]["audience"]["geography"] == ["Canada"]
    assert "Canada" in revised["revision"]["change"]
    assert "Who: MSPs in Canada with 20–100 employees." in revised["summary"]
    state = oc.objective_state(revised, prior=active, change=revised["revision"]["change"])
    assert state["revision"] == 2 and [h["revision"] for h in state["history"]] == [1, 2]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("What about the ones from last week?", False),
        ("thanks, sounds good", False),
        ("Actually make it 200 per month", True),
        ("Only Canadian companies", True),
        ("Help me reduce SLA breaches", False),  # a different objective, not a revision
        ("Wait—only Canadian companies.", True),  # spoken barge-in correction
        ("no, US only", True),
        ("can you help us with that", False),  # the pronoun "us" is not a country
    ],
)
def test_revision_detection(text, expected):
    with _tenant({"hubspot"}):
        active = oc.objective_state(oc.plan_objective(MemoryStore(), ORG, LEADS))
    assert oc.is_objective_revision(text, active) is expected


# --------------------------------------------------------------------------- text ↔ voice on the kernel


def _comparable(plan_objective: dict) -> dict:
    """The business semantics that must not diverge between modalities."""
    contract = dict(plan_objective["contract"])
    contract["baseline"] = {k: v for k, v in (contract.get("baseline") or {}).items()}
    plan = plan_objective["plan"]
    return {
        "contract": contract,
        "feasibility": plan_objective["feasibility"],
        "steps": [
            {k: s[k] for k in ("playKey", "capabilityVendors", "capabilityActions", "approvals", "measurement", "status")}
            for s in plan["steps"]
        ],
        "unlocks": plan["unlocks"],
        "ledger": plan["capabilityLedger"],
        "requiresApproval": plan["requiresApproval"],
        "audience": plan.get("audience"),
    }


async def _kernel_turn(message: str, *, spoken: bool, task_state: dict, store: MemoryStore, persisted: list):
    from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest

    state_svc = MagicMock()

    async def _update(conversation_id, org_id, updates, client=None):
        persisted.append((conversation_id, updates))

    state_svc.update_task_state = AsyncMock(side_effect=_update)
    settings = MagicMock()
    settings.cognitive_turn_kernel_enabled = True
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service", return_value=state_svc
    ), patch("app.services.cognitive_knowledge_layer.merge", AsyncMock(return_value={"prompt_section": ""})):
        kernel = CognitiveTurnKernel(settings)
        kernel._recall = AsyncMock(return_value={})  # type: ignore[method-assign]
        kernel._persist_trace = AsyncMock()  # type: ignore[method-assign]
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id=ORG,
                message=message,
                user_id="user-1",
                conversation_id="conv-shared",
                surface="voice" if spoken else "ai_chat",
                spoken_mode=spoken,
                task_state=task_state,
                client=store,
                connected_integrations=["hubspot"],
            )
        )
    return ctx


@pytest.mark.asyncio
async def test_same_objective_text_and_voice_are_semantically_equivalent():
    store = MemoryStore()
    results = {}
    with _tenant({"hubspot"}):
        for spoken in (False, True):
            persisted: list = []
            first = await _kernel_turn(LEADS, spoken=spoken, task_state={}, store=store, persisted=persisted)
            assert "objective" in first.plan, "objective planning must run on both surfaces"
            active = persisted[-1][1]["active_objective"]
            second = await _kernel_turn(
                CORRECTION, spoken=spoken, task_state={"active_objective": active}, store=store, persisted=persisted
            )
            assert second.plan["objective"]["revision"], "the correction must revise, not restart"
            results[spoken] = {
                "objective": _comparable(first.plan["objective"]),
                "revised": _comparable(second.plan["objective"]),
                "state": {k: v for k, v in persisted[-1][1]["active_objective"].items() if k != "history"},
                "prompt": "<objective_plan>" in str(second.knowledge_pack.get("prompt_section")),
            }
    assert json.dumps(results[False], sort_keys=True, default=str) == json.dumps(results[True], sort_keys=True, default=str)
    revised = results[True]["revised"]
    assert revised["contract"]["constraints"]["geography"] == ["Canada"]
    assert revised["contract"]["target"]["value"] == 150.0
    assert results[True]["state"]["revision"] == 2


# --------------------------------------------------------------------------- departments


DEPARTMENTS = [
    ("growth", LEADS, {"hubspot"}),
    ("marketing_seo", "Increase qualified organic traffic and identify the content opportunities most likely to generate pipeline.", {"google_search_console", "hubspot"}),
    ("sales", "Help us improve conversion from qualified opportunities to closed-won.", {"hubspot"}),
    ("customer_success", "Reduce preventable churn among our highest-value customers.", {"hubspot", "stripe"}),
    ("msp", "Reduce SLA breaches and improve first-response performance.", {"freshservice"}),
    ("finance", "Improve collections and reduce overdue receivables.", {"quickbooks", "gmail"}),
]


@pytest.mark.parametrize("department,text,vendors", DEPARTMENTS)
def test_every_department_runs_through_the_same_objective_loop(department, text, vendors):
    with _tenant(vendors):
        assert oc.looks_like_objective(text), text
        brief = oc.plan_objective(MemoryStore(), ORG, text)
    contract = brief["contract"]
    assert contract.get("metricKey"), f"{department}: no canonical metric"
    assert contract["baseline"]["value"] is None  # unknown, never a fabricated zero
    assert brief["feasibility"]["targetIsNotAPromise"] is True
    assert brief["plan"]["steps"], f"{department}: no plan"
    assert brief["plan"]["capabilityLedger"]
    assert any(r["department"] for r in brief["resources"])


def test_spoken_interruption_correction_keeps_everything_it_does_not_name():
    """'Wait, only Canadian companies' while Gravitre is speaking revises the audience only."""
    with _tenant({"hubspot"}):
        active = oc.objective_state(oc.plan_objective(MemoryStore(), ORG, LEADS))
        revised = oc.revise_objective(
            MemoryStore(), ORG, active, "Wait—only Canadian companies.", environment_name="production", settings=None
        )
    assert revised["plan"]["audience"] == {"geography": ["Canada"]}
    assert revised["contract"]["target"]["value"] == 150
    assert revised["contract"]["metricKey"] == active["metricKey"]
    assert set(revised["revision"]["preserved"]) >= {"metricKey", "definition", "sourceSystem"}
