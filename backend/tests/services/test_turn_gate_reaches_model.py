"""Site 8 regression: `classify_turn_shape` must actually reach the model router.

The dormant call here failed *closed* (shape="task_shaped"), so nothing ever
looked broken — but it decided 71.9% of real user turns, measured over 30 days
of production messages in `backend/scripts/probe_turn_gate_reach.py`. The
heuristic assigned "mixed" once in 1000 turns, meaning the mixed social-ack
feature in `_maybe_prepend_mixed_social_ack` was effectively waiting on a call
that never ran.

`get_model_router` is imported inside the function, so the patch target is the
source module rather than this one. Every fake enforces the real zero-argument
signature: a reintroduced `get_model_router(settings)` must fail loudly here
instead of being absorbed by a permissive mock and then swallowed by the
handler, which is exactly how this class of bug survived on site 7.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import conversational_turn_gate as gate

# Deliberately carries no data/connector/social/venting/meta signal, so the
# heuristic declines and the model is the real decider. Asserted, not assumed:
# test_ambiguous_message_really_reaches_the_model_tier keeps it honest.
AMBIGUOUS = "Walk me through how we should approach the Q3 board deck."
MIXED_TEXT = "Appreciate the fast turnaround yesterday — pull the latest pipeline numbers."


class _StrictRouter:
    def __init__(self, payload: Any, calls: list[dict[str, Any]]) -> None:
        self._payload = payload
        self._calls = calls

    async def complete(self, **kwargs: Any) -> SimpleNamespace:
        self._calls.append(kwargs)
        if isinstance(self._payload, dict):
            return SimpleNamespace(parsed=self._payload, content=json.dumps(self._payload))
        return SimpleNamespace(parsed=None, content=self._payload)


@pytest.fixture
def routed(monkeypatch):
    """Install a factory that enforces the real zero-argument signature."""

    def _install(payload: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def _factory(*args: Any, **kwargs: Any):
            assert not args and not kwargs, (
                "get_model_router takes no arguments; passing one is the dormancy "
                f"bug this test exists to catch. got args={args!r} kwargs={kwargs!r}"
            )
            return _StrictRouter(payload, calls)

        monkeypatch.setattr("app.services.model_router.get_model_router", _factory)
        return calls

    return _install


def test_ambiguous_message_really_reaches_the_model_tier():
    """Guards the premise: if the heuristic ever claims this text, the tests below go vacuous."""
    assert gate.heuristic_turn_shape(AMBIGUOUS) is None


@pytest.mark.asyncio
async def test_model_is_called_with_zero_arguments(routed):
    calls = routed({"shape": "conversational", "reason": "chit", "category": "small_talk"})

    result = await gate.classify_turn_shape(AMBIGUOUS, settings=object(), org_id="org-1")

    assert len(calls) == 1, "the model tier never ran — the call is still dormant"
    assert result.used_model is True


@pytest.mark.asyncio
async def test_model_verdict_beats_the_fail_closed_default(routed):
    """The whole point: a genuinely conversational turn must not be forced task_shaped."""
    routed({"shape": "conversational", "reason": "greeting-ish", "category": "small_talk"})

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.shape == "conversational"
    assert result.category == "small_talk"


@pytest.mark.asyncio
async def test_mixed_shape_and_split_survive(routed):
    """Caller 2 (_maybe_prepend_mixed_social_ack) keys entirely off shape == mixed."""
    routed(
        {
            "shape": "mixed",
            "reason": "social plus task",
            "social_portion": "Appreciate the fast turnaround yesterday",
            "task_portion": "pull the latest pipeline numbers",
            "category": "thanks",
        }
    )

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.shape == "mixed"
    assert result.social_portion == "Appreciate the fast turnaround yesterday"
    assert result.task_portion == "pull the latest pipeline numbers"


@pytest.mark.asyncio
async def test_unparsed_json_content_is_still_honored(routed):
    """Providers that ignore response_format return raw text; that must not be discarded."""
    routed(json.dumps({"shape": "conversational", "category": "banter"}))

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.shape == "conversational"
    assert result.category == "banter"


@pytest.mark.asyncio
async def test_unknown_shape_falls_back_to_task_shaped(routed):
    routed({"shape": "wat", "reason": "nonsense"})

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.shape == "task_shaped"


@pytest.mark.asyncio
async def test_empty_task_portion_defaults_to_the_message(routed):
    routed({"shape": "task_shaped", "reason": "r", "task_portion": ""})

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.task_portion == AMBIGUOUS


@pytest.mark.asyncio
async def test_router_failure_still_fails_closed(monkeypatch):
    """Degradation must stay safe: real work never gets dropped into chitchat."""

    def _boom(*args: Any, **kwargs: Any):
        raise RuntimeError("provider down")

    monkeypatch.setattr("app.services.model_router.get_model_router", _boom)

    result = await gate.classify_turn_shape(AMBIGUOUS)

    assert result.shape == "task_shaped"
    assert result.used_model is False
    assert "model_unavailable" in result.reason


@pytest.mark.asyncio
async def test_heuristic_hit_never_pays_for_the_model(monkeypatch):
    """Cost guard: greetings must not start routing through a model call."""

    def _boom(*args: Any, **kwargs: Any):
        raise AssertionError("heuristic path must not reach the model")

    monkeypatch.setattr("app.services.model_router.get_model_router", _boom)

    result = await gate.classify_turn_shape("hey there!")

    assert result.shape == "conversational"
    assert result.used_model is False


@pytest.mark.asyncio
async def test_conversation_summary_reaches_the_prompt(routed):
    calls = routed({"shape": "conversational", "category": "small_talk"})

    await gate.classify_turn_shape(AMBIGUOUS, conversation_summary="talked about renewals")

    assert "talked about renewals" in calls[0]["prompt"]


@pytest.mark.asyncio
async def test_org_id_is_forwarded_for_attribution(routed):
    calls = routed({"shape": "task_shaped"})

    await gate.classify_turn_shape(AMBIGUOUS, org_id="org-42")

    assert calls[0]["org_id"] == "org-42"
