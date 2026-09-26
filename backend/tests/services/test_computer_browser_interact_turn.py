"""Governed Computer Use interact — HMAC compile, confirm, no HubSpot WRITE."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.action_catalog.registry import clear_action_spec_cache, get_action_spec, get_vendor_catalog
from app.services.computer_browser_interact_turn import (
    ACTION_KEY,
    computer_interact_should_compile,
    match_computer_browser_interact,
    try_computer_browser_interact_turn,
)
from app.services.computer_execution import classify_execution_strategy


def _refresh_catalog() -> None:
    get_vendor_catalog.cache_clear()
    clear_action_spec_cache()


def test_interact_intent_is_not_hubspot_write() -> None:
    assert match_computer_browser_interact(
        "Fill the httpbin.org form and submit. Do not use HubSpot."
    )
    assert match_computer_browser_interact("Create a HubSpot contact named Probe") is False
    assert classify_execution_strategy(invoke_action="hubspot.contacts.create", has_action_spec=True) == "api_native"


def test_browser_agent_interact_is_f1_write_spec() -> None:
    _refresh_catalog()
    spec = get_action_spec(ACTION_KEY)
    assert spec is not None
    assert spec.kind == "write"
    assert spec.requires_approval is True
    assert spec.risk_class == "browser_interact"


@pytest.mark.asyncio
async def test_interact_compile_stages_hmac_pending_without_submit() -> None:
    _refresh_catalog()
    turn = await try_computer_browser_interact_turn(
        message="Fill the httpbin.org form and submit. Public browser only. Do not use HubSpot.",
        org_id="f07e57c0-1501-4000-8000-c04e57a00001",
        client=object(),
        settings=MagicMock(),
        connected_integrations=["hubspot"],
        task_state={},
        user_id="11111111-1111-4111-8111-111111111111",
        conversation_id="conv-cu-interact",
    )
    assert turn is not None
    assert turn["stop_pipeline"] is True
    assert turn["dialogue_mode"] == "confirm"
    assert turn["writes_started"] is False
    assert turn["provider_reinvoked"] is False
    pending = (turn["task_state"] or {}).get("pending_task") or {}
    assert pending.get("status") == "awaiting_confirm"
    params = pending.get("params") or {}
    assert params.get("invoke_action") == ACTION_KEY
    digest = (params.get("preflight_proof") or {}).get("proof_digest")
    assert digest
    assert computer_interact_should_compile("yes", turn["task_state"]) is True


@pytest.mark.asyncio
async def test_interact_confirm_without_hmac_does_not_submit() -> None:
    turn = await try_computer_browser_interact_turn(
        message="yes",
        org_id="org-1",
        client=object(),
        settings=MagicMock(),
        connected_integrations=[],
        task_state={
            "pending_task": {
                "status": "awaiting_confirm",
                "invoke_action": ACTION_KEY,
                "params": {"invoke_action": ACTION_KEY, "args": {"url": "https://httpbin.org/forms/post"}},
            }
        },
    )
    assert turn is not None
    assert turn["writes_started"] is False
    assert turn["workflow_status"] == "blocked"


@pytest.mark.asyncio
async def test_interact_confirm_invokes_playwright_with_hmac() -> None:
    _refresh_catalog()
    compiled = await try_computer_browser_interact_turn(
        message="Fill the httpbin.org form and submit. Do not use HubSpot.",
        org_id="org-1",
        client=object(),
        settings=MagicMock(),
        connected_integrations=["hubspot"],
        task_state={},
        user_id="11111111-1111-4111-8111-111111111111",
    )
    assert compiled is not None
    with patch(
        "app.services.browser_agent_service.browser_agent_interact",
        new_callable=AsyncMock,
        return_value={
            "url": "https://httpbin.org/forms/post",
            "mode": "playwright_interact",
            "steps": [{"ok": True}],
            "text": "Custname: Gravitre isolated test",
        },
    ) as mock_interact:
        confirmed = await try_computer_browser_interact_turn(
            message="yes",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state=compiled["task_state"],
            user_id="11111111-1111-4111-8111-111111111111",
        )
    assert confirmed is not None
    assert confirmed["writes_started"] is True
    assert confirmed["workflow_status"] == "completed"
    mock_interact.assert_awaited_once()
    kwargs = mock_interact.await_args.kwargs
    assert kwargs.get("hmac_verified") is True
    assert kwargs.get("approval_id")
    obs = (confirmed["task_state"] or {}).get("execution_observations") or []
    assert obs and obs[-1].get("success") is True


@pytest.mark.asyncio
async def test_interact_confirm_surfaces_playwright_failure() -> None:
    from app.services.browser_agent_service import BrowserAgentError

    _refresh_catalog()
    compiled = await try_computer_browser_interact_turn(
        message="Fill the httpbin.org form and submit. Do not use HubSpot.",
        org_id="org-1",
        client=object(),
        settings=MagicMock(),
        connected_integrations=["hubspot"],
        task_state={},
        user_id="11111111-1111-4111-8111-111111111111",
    )
    assert compiled is not None
    with patch(
        "app.services.browser_agent_service.browser_agent_interact",
        new_callable=AsyncMock,
        side_effect=BrowserAgentError("selector timed out", code="playwright_failed"),
    ):
        confirmed = await try_computer_browser_interact_turn(
            message="yes",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state=compiled["task_state"],
            user_id="11111111-1111-4111-8111-111111111111",
        )
    assert confirmed is not None
    assert confirmed["stop_pipeline"] is True
    assert confirmed["workflow_status"] == "failed"
    assert "selector timed out" in str(confirmed.get("message") or "")
    pending = (confirmed["task_state"] or {}).get("pending_task") or {}
    assert pending.get("status") == "failed"


def test_hmac_interact_confirm_runs_before_intent_gateway_shortcut() -> None:
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "app" / "operators" / "agent_intelligence.py"
    ).read_text(encoding="utf-8")
    first_interact = text.find("try_computer_browser_interact_turn")
    shortcut = text.find('gateway.action == "shortcut"')
    emit_def = text.find("async def _emit_compiled_operational_short_circuit")
    persona_init = text.find('persona = {\n            "persona_key"')
    assert emit_def >= 0
    assert 0 <= persona_init < first_interact
    assert 0 <= first_interact < shortcut
    assert "computer_browser_interact_confirm" in text


@pytest.mark.asyncio
async def test_gateway_falls_through_hmac_interact_yes() -> None:
    from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway

    pending = {
        "pending_task": {
            "status": "awaiting_confirm",
            "invoke_action": ACTION_KEY,
            "params": {"invoke_action": ACTION_KEY},
        }
    }
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message="yes",
            spoken_mode=True,
            task_state=pending,
            org_id="org",
            user_id="user-a",
            conversation_id="conv-a",
        )
    )
    assert decision.action == "fallthrough"
    assert decision.reason == "pending_write_confirm"


def test_enrich_keeps_interact_hmac_invoke_action() -> None:
    from app.services.execution_plan_adapters import enrich_task_state_patch
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

    plan = ExecutionPlan(
        plan_id="plan-int",
        summary="Fill the public httpbin form after approval",
        source="computer_execution",
        steps=[
            ExecutionStep(
                step_id="computer_interact",
                title="Public browser form fill",
                kind="write",
                connector_id="browser_agent",
                action_key=ACTION_KEY,
            )
        ],
    )
    pending = {
        "status": "awaiting_confirm",
        "invoke_action": ACTION_KEY,
        "params": {
            "invoke_action": ACTION_KEY,
            "args": {"url": "https://httpbin.org/forms/post"},
            "preflight_proof": {"status": "ready", "proof_digest": "abc"},
        },
    }
    out = enrich_task_state_patch(
        {"execution_plan": plan.as_dict(), "pending_task": pending},
        current_state={},
    )
    stored = out.get("pending_task") or {}
    params = stored.get("params") if isinstance(stored.get("params"), dict) else {}
    assert stored.get("status") == "awaiting_confirm"
    assert params.get("invoke_action") == ACTION_KEY or stored.get("invoke_action") == ACTION_KEY
    assert computer_interact_should_compile("yes", out) is True
