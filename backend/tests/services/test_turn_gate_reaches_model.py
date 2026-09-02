"""Site 8: the turn-shape gate's model tier is RETIRED — it must call no model.

History matters here, because this file previously asserted the opposite.

The gate's `get_model_router(settings or get_settings())` call was dormant
(TypeError swallowed on every invocation). It was fixed and mutation-proven, and
then its production reach was measured at NEAR ZERO: 12 live turns, including
turns provably past the gate's caller, produced zero `turn.shape.classified`
events. The earlier "71.9% of turns" figure turned out to be the heuristic's
deferral rate, not production reach.

The value of the model tier was then measured rather than assumed
(docs/delivery/turn-shape-gate-value.md), and Cesar chose: keep the heuristic,
retire the model tier. The reasons, all evidenced:

  - the unified-turn reasoning model already decides conversational quality; the
    probe replies proved it while this gate was dormant
  - the gate's whole-turn consumer is off whenever LIVE is enabled, and is the
    documented UNIFIED_TURN_LIVE_ENABLED=false rollback
  - LIVE's own shape hint calls heuristic_turn_shape DIRECTLY, so it never stood
    to gain from the model tier

So the invariant inverts: the gate must be free, deterministic, and must never
reach a model. The tests below enforce that, and the heuristic's own behaviour —
which every remaining consumer depends on — is pinned unchanged.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.conversational_turn_gate import (
    classify_turn_shape,
    heuristic_turn_shape,
)


@pytest.fixture
def forbid_model(monkeypatch):
    """Any model call is now a regression, so make one impossible to miss."""
    calls: list[str] = []

    def _boom(*args: Any, **kwargs: Any):
        calls.append("called")
        raise AssertionError(
            "the turn-shape gate model tier is retired; it must not call a model"
        )

    monkeypatch.setattr("app.services.model_router.get_model_router", _boom)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "so anyway I was thinking about the thing we discussed",
        "hmm",
        "well that is one way to look at it I suppose",
        "I mean, sure, if that is what makes sense",
        "the whole situation has been a lot lately honestly",
    ],
)
async def test_ambiguous_messages_never_reach_a_model(forbid_model, message: str) -> None:
    """These are exactly the messages the heuristic declines and used to defer."""
    decision = await classify_turn_shape(message)

    assert forbid_model == [], "no model call may happen for an ambiguous message"
    assert decision.used_model is False
    assert decision.shape == "task_shaped", "must fail closed, not into chitchat"
    assert decision.reason == "heuristic_declined_model_tier_retired"


@pytest.mark.asyncio
async def test_declined_turn_keeps_the_message_as_task_portion(forbid_model) -> None:
    decision = await classify_turn_shape("  so anyway about that thing  ")

    assert decision.task_portion == "so anyway about that thing"
    assert decision.category == "other"


@pytest.mark.asyncio
async def test_no_audit_is_written_without_a_real_actor(forbid_model) -> None:
    """actor_id=None would be silently dropped; the gate must not bother."""
    writes: list[dict[str, Any]] = []

    async def _capture(**kwargs: Any) -> None:
        writes.append(kwargs)

    import app.workflows.audit as audit_mod

    original = audit_mod.write_audit_event
    audit_mod.write_audit_event = _capture  # type: ignore[assignment]
    try:
        await classify_turn_shape("hmm, anyway", user_id=None)
    finally:
        audit_mod.write_audit_event = original  # type: ignore[assignment]

    assert writes == []


@pytest.mark.asyncio
async def test_declined_turn_records_the_retirement_in_the_audit(forbid_model) -> None:
    """The instrument stays: it is the only visibility into this component."""
    writes: list[dict[str, Any]] = []

    async def _capture(**kwargs: Any) -> None:
        writes.append(kwargs)

    import app.workflows.audit as audit_mod

    original = audit_mod.write_audit_event
    audit_mod.write_audit_event = _capture  # type: ignore[assignment]
    try:
        await classify_turn_shape(
            "hmm, anyway",
            user_id="11111111-1111-4111-8111-111111111111",
            call_site="unit_test",
        )
    finally:
        audit_mod.write_audit_event = original  # type: ignore[assignment]

    assert len(writes) == 1
    md = writes[0]["metadata"]
    assert md["usedModel"] is False
    assert md["modelTierRetired"] is True
    assert md["shape"] == "task_shaped"
    assert md["callSite"] == "unit_test"
    assert writes[0]["actor_id"] == "11111111-1111-4111-8111-111111111111"


# --- the heuristic itself must be unchanged: every live consumer depends on it ---
#
# is_task_shaped_for_retrieval (LIVE retrieval hint) and
# maybe_social_ack_with_pending_note both call heuristic_turn_shape directly.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message,shape",
    [
        ("thanks!", "conversational"),
        ("hey there", "conversational"),
        ("good morning", "conversational"),
        ("list my hubspot deals", "task_shaped"),
        ("how are the deals looking", "task_shaped"),
    ],
)
async def test_heuristic_decisions_still_short_circuit(
    forbid_model, message: str, shape: str
) -> None:
    decision = await classify_turn_shape(message)

    assert forbid_model == []
    assert decision.shape == shape
    assert decision.used_model is False


def test_heuristic_still_returns_none_when_it_cannot_decide() -> None:
    """Pins the contract the retirement relies on: None means 'declined'."""
    assert heuristic_turn_shape("so anyway I was thinking") is None


def test_heuristic_still_decides_the_clear_cases() -> None:
    thanks = heuristic_turn_shape("thanks, that helped")
    task = heuristic_turn_shape("show me my open deals in hubspot")

    assert thanks is not None and thanks.shape == "conversational"
    assert task is not None and task.shape == "task_shaped"


def test_gate_module_no_longer_imports_a_model_router() -> None:
    """Structural: the retirement must be real, not just unreached at runtime."""
    from pathlib import Path

    import app.services.conversational_turn_gate as gate

    src = Path(gate.__file__).read_text(encoding="utf-8")

    assert "get_model_router" not in src, (
        "the model tier is retired; a model router reference means it came back"
    )
    assert "_model_turn_shape" not in src
