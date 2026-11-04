"""PR #601: voice provider errors must never masquerade as user ambiguity."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.voice_model_failure import unavailable_voice_model_reply


def _result(kind="error", error="AllProvidersFailedError", **breakdown):
    return SimpleNamespace(outcome_kind=kind, error=error, latency_breakdown=breakdown)


def test_recognized_model_failure_gets_specific_honest_voice_response():
    for kind in (
        "AllProvidersFailedError",
        "ProviderUnavailableError",
        "ProviderAuthenticationUnavailable",
        "AuthenticationError",
        "PermissionDeniedError",
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
    ):
        result = unavailable_voice_model_reply(_result(error=kind))
        assert result is not None
        assert "model service is unavailable" in result
        assert "haven't completed the task" in result
        assert "clarify" not in result.lower()
        assert "which item" not in result.lower()


def test_no_exception_bodies_credit_or_provider_identifiers_leak_to_voice():
    secret = "sk-test-secret-never-spoken"
    for status in ("insufficient_credits", "billing", "rate_limit", "provider_unavailable"):
        result = unavailable_voice_model_reply(
            _result(error="APIStatusError", provider_error_category=status)
        )
        assert result
        assert secret not in result
        assert "anthropic" not in result.lower()
        assert "credit" not in result.lower()


def test_non_provider_errors_and_healthy_replies_preserve_existing_behavior():
    assert unavailable_voice_model_reply(_result(error="TypeError")) is None
    assert unavailable_voice_model_reply(_result(error="APIStatusError")) is None
    assert unavailable_voice_model_reply(_result(kind="clarifying_question")) is None
    assert unavailable_voice_model_reply(_result(kind="conversational_reply")) is None
    assert unavailable_voice_model_reply(
        SimpleNamespace(outcome_kind="error", error="TypeError", latency_breakdown=None)
    ) is None


def test_unified_voice_error_branch_precedes_classical_fallthrough():
    source = (
        Path(__file__).resolve().parents[2]
        / "app/services/unified_turn_reasoning_service.py"
    ).read_text()
    voice = source.index('if spoken_mode and result.outcome_kind == "error":')
    fallback = source.index('if result.outcome_kind in {"skipped", "error"}:', voice)
    assert voice < fallback
    assert "unavailable_voice_model_reply(result)" in source[voice:fallback]
    assert "return _unified_live_turn_payload(result, task_state)" in source[voice:fallback]
    assert "error=type(exc).__name__" in source
