"""Assistant usage is recorded once per turn, not once per org per billing period.

_record_assistant_billing used model_call_id or org_id as the idempotency
anchor. model_call_id is always None on the assistant path, so every turn in a
period derived the same key and the unique index dropped all but the first.
Production showed one assistant usage row per org per month from late June.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.billing.service import derive_idempotency_key
from app.routers import assistant
from app.services.model_router import ModelResponse

PERIOD = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _key(source_id: str) -> str:
    return derive_idempotency_key(
        "org-1", "ai_credits", PERIOD, {"source": "assistant", "source_id": source_id}
    )


def test_two_turns_get_two_keys_and_a_retry_keeps_one():
    a = assistant.assistant_billing_source_id(None, "msg-a")
    b = assistant.assistant_billing_source_id(None, "msg-b")
    assert _key(a) != _key(b)
    assert _key(a) == _key(assistant.assistant_billing_source_id(None, "msg-a"))
    assert "org-1" not in a and "org-1" not in b


def test_model_call_id_wins_and_missing_ids_never_collapse_to_the_org():
    assert assistant.assistant_billing_source_id("mc-1", "msg-a") == "mc-1"
    x = assistant.assistant_billing_source_id(None, None)
    y = assistant.assistant_billing_source_id(None, None)
    assert x != y and x.startswith("turn:")


def _response():
    return ModelResponse(
        provider="openai", model="gpt-5.4-mini", content="hi", input_tokens=10,
        output_tokens=5, latency_ms=10, cost_usd=0.0, model_call_id=None,
    )


@pytest.mark.asyncio
async def test_record_uses_the_turn_and_labels_estimates():
    calls: list[dict] = []
    with (
        patch.object(assistant, "get_supabase_client", return_value=MagicMock()),
        patch.object(assistant, "get_plan_for_org", return_value={"name": "pro"}),
        patch.object(assistant, "get_current_period", return_value=(PERIOD, PERIOD)),
        patch.object(assistant, "apply_usage_with_overage", side_effect=lambda **kw: calls.append(kw)),
    ):
        await assistant._record_assistant_billing(SimpleNamespace(), "org-1", _response(), turn_id="msg-a")
        await assistant._record_assistant_billing(SimpleNamespace(), "org-1", _response(), turn_id="msg-b")
    assert [c["metadata"]["source_id"] for c in calls] == ["turn:msg-a", "turn:msg-b"]
    assert all(c["metadata"]["usage_estimated"] is True for c in calls)


@pytest.mark.asyncio
async def test_zero_provider_usage_does_not_trigger_minimum_credit_charge():
    measured = ModelResponse(provider="openai", model="gpt-5.5", content="",
                             input_tokens=0, output_tokens=0, latency_ms=0,
                             cost_usd=0, model_call_id="call-zero")
    with patch.object(assistant, "get_supabase_client") as client:
        assert await assistant._record_assistant_billing(SimpleNamespace(), "org-1", measured) is True
    client.assert_not_called()


@pytest.mark.asyncio
async def test_measured_call_uses_provider_period_at_month_boundary():
    measured = ModelResponse(provider="openai", model="gpt-5.5", content="",
                             input_tokens=100, output_tokens=20, latency_ms=10,
                             cost_usd=.01, model_call_id="call-october")
    with (
        patch.object(assistant, "get_supabase_client", return_value=MagicMock()),
        patch.object(assistant, "get_plan_for_org", return_value={}),
        patch.object(assistant, "apply_usage_with_overage") as apply,
    ):
        assert await assistant._record_assistant_billing(
            SimpleNamespace(), "org-1", measured,
            period_at=datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc),
        ) is True
    assert apply.call_args.kwargs["period_start"].isoformat() == "2026-10-01"


@pytest.mark.asyncio
async def test_assistant_atomic_requires_generic_lock_even_without_model_call():
    with (
        patch.object(assistant, "get_supabase_client", return_value=MagicMock()),
        patch.object(assistant, "get_plan_for_org", return_value={}),
        patch.object(assistant, "apply_usage_with_overage") as apply,
        patch.object(assistant, "_log_assistant_guardrail_event") as guardrail,
    ):
        ok = await assistant._record_assistant_billing(
            SimpleNamespace(assistant_billing_atomic_enabled=True, usage_atomic_enabled=False),
            "org-1", _response(), turn_id="msg-a",
        )
    assert ok is False
    apply.assert_not_called()
    guardrail.assert_called_once()
