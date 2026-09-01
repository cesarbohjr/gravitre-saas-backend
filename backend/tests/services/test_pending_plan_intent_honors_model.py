"""Site 6 regression: the model's verdict must beat the fallback in
`classify_pending_plan_intent`.

While `_model_pending_intent` was dormant (calling the zero-arg
`get_model_router` with an argument, TypeError swallowed by the enclosing
handler), the modify-hint branch fell through to a hardcoded "modify". A reply
meaning cancel that happened to contain a modify hint therefore left a
destructive plan pending instead of dropping it.

Every assertion here fails if that call goes dormant again, because each one
requires the model's answer to actually reach the return value.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services import conversation_turn_controller as ctc


class _Response:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self.parsed = parsed
        self.content = ""


class _Router:
    """Records how it was constructed so a re-introduced arg is visible."""

    def __init__(self, intent: str, calls: list[dict[str, Any]]) -> None:
        self._intent = intent
        self._calls = calls

    async def complete(self, **kwargs: Any) -> _Response:
        self._calls.append(kwargs)
        return _Response({"intent": self._intent, "reason": "test"})


@pytest.fixture
def routed(monkeypatch):
    """Patch the router factory, asserting it is called with zero arguments."""

    def _install(intent: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def _factory(*args: Any, **kwargs: Any):
            # This is the actual defect being guarded: the real factory takes no
            # arguments, so any caller passing one raised TypeError and was
            # silently swallowed. Fail loudly instead of degrading.
            assert not args and not kwargs, (
                "get_model_router must be called with no arguments; got "
                f"args={args!r} kwargs={kwargs!r}"
            )
            return _Router(intent, calls)

        import app.services.model_router as mr

        monkeypatch.setattr(mr, "get_model_router", _factory)
        return calls

    return _install


_PLAN = {"goal": "Create a HubSpot list of MSP prospects and add matched deals"}
_TASK = {"status": "awaiting_confirm", "type": "awaiting_confirm"}


async def _classify(message: str) -> str:
    return await ctc.classify_pending_plan_intent(
        message,
        current_plan=_PLAN,
        pending_task=_TASK,
        use_model=True,
    )


# The reply at the heart of the defect: long enough not to match the
# short-utterance cancel patterns, contains "don't" so the modify-hint branch
# claims it, and unambiguously means cancel.
_CANCEL_VIA_MODIFY_HINT = (
    "don't bother with that, we're going a completely different direction now"
)


@pytest.mark.asyncio
async def test_modify_hint_reply_meaning_cancel_is_cancelled(routed):
    """The regression itself. Dormant, this returned 'modify' and kept the plan."""
    routed("cancel")
    assert ctc.re_modify_hint(_CANCEL_VIA_MODIFY_HINT) is True
    assert await _classify(_CANCEL_VIA_MODIFY_HINT) == "cancel"


@pytest.mark.asyncio
async def test_modify_hint_reply_meaning_continue_is_continued(routed):
    routed("continue")
    assert await _classify("just go ahead with it as planned") == "continue"


@pytest.mark.asyncio
async def test_modify_hint_still_falls_back_to_modify_when_model_unclear(routed):
    """The fallback is correct when the model genuinely cannot decide."""
    routed("unclear")
    assert await _classify(_CANCEL_VIA_MODIFY_HINT) == "modify"


@pytest.mark.asyncio
async def test_general_path_reply_is_classified_by_model(routed):
    """No modify hint, so this takes the branch whose fallback is 'unclear'."""
    msg = "hold off, I need to run this past our finance lead before anything happens"
    assert ctc.re_modify_hint(msg) is False
    routed("cancel")
    assert await _classify(msg) == "cancel"


@pytest.mark.asyncio
async def test_general_path_falls_back_to_unclear_when_model_unclear(routed):
    routed("unclear")
    msg = "hold off, I need to run this past our finance lead before anything happens"
    assert await _classify(msg) == "unclear"


@pytest.mark.asyncio
async def test_model_is_not_consulted_for_unambiguous_replies(routed):
    """Cost and latency guard: the regex fast path must still short-circuit."""
    calls = routed("cancel")
    assert await _classify("yes") == "continue"
    assert await _classify("cancel") == "cancel"
    assert calls == [], "fast-path replies must not reach the model"


@pytest.mark.asyncio
async def test_model_not_consulted_when_use_model_false(routed):
    calls = routed("cancel")
    result = await ctc.classify_pending_plan_intent(
        _CANCEL_VIA_MODIFY_HINT,
        current_plan=_PLAN,
        pending_task=_TASK,
        use_model=False,
    )
    assert result == "modify"
    assert calls == []


@pytest.mark.asyncio
async def test_no_plan_and_no_task_does_not_consult_model(routed):
    calls = routed("cancel")
    msg = "hold off, I need to run this past our finance lead before anything happens"
    result = await ctc.classify_pending_plan_intent(
        msg, current_plan=None, pending_task=None, use_model=True
    )
    assert result == "unclear"
    assert calls == []


@pytest.mark.asyncio
async def test_classification_uses_the_fast_cheap_tier(routed):
    """This runs on every pending reply; it must not silently become expensive."""
    from app.services.model_router import TaskType

    calls = routed("cancel")
    await _classify(_CANCEL_VIA_MODIFY_HINT)
    assert calls, "the model should have been consulted"
    assert calls[0]["task_type"] is TaskType.CLASSIFICATION
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["max_tokens"] <= 120


@pytest.mark.asyncio
async def test_plan_goal_is_given_to_the_model(routed):
    """Without the goal the model cannot tell what 'that' refers to."""
    calls = routed("cancel")
    await _classify(_CANCEL_VIA_MODIFY_HINT)
    prompt = calls[0]["prompt"]
    assert "MSP prospects" in prompt
    assert _CANCEL_VIA_MODIFY_HINT in prompt


@pytest.mark.asyncio
async def test_router_failure_degrades_instead_of_raising(monkeypatch):
    """Graceful degradation must survive — but loudly, per the Phase 1 guard."""

    def _boom(*args: Any, **kwargs: Any):
        raise RuntimeError("all providers unavailable")

    import app.services.model_router as mr

    monkeypatch.setattr(mr, "get_model_router", _boom)
    assert await _classify(_CANCEL_VIA_MODIFY_HINT) == "modify"
