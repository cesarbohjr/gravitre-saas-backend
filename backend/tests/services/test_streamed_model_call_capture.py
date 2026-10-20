"""Measured provider calls are the only sources of streamed AI credits."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

from app.services.cost_attribution import (
    MeasuredModelCall, ModelCallCapture, capture_model_calls, record_measured_model_call,
)
from app.services.model_router import ModelResponse, ModelRouter, TaskType


def test_capture_deduplicates_and_enforces_org_boundary():
    capture = ModelCallCapture("org-a")
    one = MeasuredModelCall("call-1", "org-a", "openai", "gpt-5.5", 100, 20, 5, .01)
    foreign = MeasuredModelCall("call-2", "org-b", "openai", "gpt-5.5", 100, 20, 5, .01)
    with capture_model_calls(capture):
        record_measured_model_call(one)
        record_measured_model_call(one)
        record_measured_model_call(foreign)
    record_measured_model_call(foreign)
    assert capture.calls == [one]


def test_in_process_response_cache_is_scoped_to_org():
    router = object.__new__(ModelRouter)
    common = (TaskType.DECISION_REASONING, "same prompt", "system", None, 50,
              "gpt-5.5", [{"role": "user", "content": "same context"}])
    assert router._cache_key(*common, "org-a") != router._cache_key(*common, "org-b")


@pytest.mark.asyncio
async def test_model_call_capture_preserves_provider_tokens_and_id():
    router = object.__new__(ModelRouter)
    router.settings = MagicMock()
    capture = ModelCallCapture("org-a")
    response = ModelResponse(provider="anthropic", model="claude-haiku-5-5",
                             content="done", input_tokens=321, output_tokens=47,
                             latency_ms=80, cost_usd=.002)
    with (
        patch("app.services.model_router.get_supabase_client", return_value=MagicMock()),
        patch("app.services.cost_attribution.insert_model_call",
              return_value=SimpleNamespace(data=[{"id": "call-321", "created_at": "2026-10-31T23:59:59Z"}])),
        capture_model_calls(capture),
    ):
        assert await router._log_model_call("org-a", TaskType.DECISION_REASONING, response) == "call-321"

    assert [(c.id, c.model, c.input_tokens, c.output_tokens) for c in capture.calls] == [
        ("call-321", "claude-haiku-5-5", 321, 47),
    ]
    assert capture.calls[0].created_at == datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_in_process_model_cache_is_not_captured_as_billable():
    router = object.__new__(ModelRouter)
    router.settings = MagicMock()
    capture = ModelCallCapture("org-a")
    response = ModelResponse(provider="openai", model="gpt-5.5", content="cached",
                             input_tokens=100, output_tokens=20, latency_ms=1, cost_usd=.01)
    with (
        patch("app.services.model_router.get_supabase_client", return_value=MagicMock()),
        patch("app.services.cost_attribution.insert_model_call",
              return_value=SimpleNamespace(data=[{"id": "cached-row"}])),
        capture_model_calls(capture),
    ):
        assert await router._log_model_call("org-a", TaskType.DECISION_REASONING,
                                             response, billable=False) == "cached-row"
    assert capture.calls == []
