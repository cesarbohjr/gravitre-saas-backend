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
