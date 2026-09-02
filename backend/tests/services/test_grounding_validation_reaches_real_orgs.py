"""Who actually gets grounding validation, and why agent mode does not.

Two separate facts, both measured, both worth pinning so neither is
rediscovered the hard way.

1. There is a real, open coverage gap. resolve_effective_intelligence_mode
   upgrades BOTH standard and reasoning to agent whenever a connector is
   connected, and leaves fast as fast. So a connector-connected org can only
   ever reach {fast, agent}, and the validation set is {standard, reasoning}:
   the intersection is empty. Grounding validation is unreachable for every org
   with a connector. Zero `answer.grounding.validated` events across the whole
   measurement window agreed.

2. Closing that gap by adding agent to the set does not work, and this was
   established live rather than argued. Tried at 1e94e644, reverted same day
   (docs/delivery/grounding-validator-latency.json): p50 9309ms / p95 10131ms
   added against a generation p50 of 3123ms, and 3 of 3 agent-mode answers
   replaced, one of them falling through to SAFE_FALLBACK.

   The cause is structural. agent mode is where answers come from TOOLS while
   RAG chunks are incidentally present, so the validator compares a tool-derived
   conclusion against unrelated knowledge chunks and correctly finds it
   unsupported. It cannot judge those turns, and a config flag cannot teach it to.

So these tests deliberately assert the exclusion AND the gap. If someone adds
agent to the default set again, the failure message should send them to the
measurement rather than to a merge conflict.
"""
from __future__ import annotations

import pytest

from app.operators.assistant_mode_config import resolve_effective_intelligence_mode
from app.services.intelligence_engine_settings import (
    IntelligenceEngineSettings,
    validation_enabled_for_mode,
)


def _settings(performance_mode: str = "balanced") -> IntelligenceEngineSettings:
    return IntelligenceEngineSettings(
        validation_enabled=True,
        performance_mode=performance_mode,
    )


def test_only_fast_and_agent_are_reachable_with_connectors() -> None:
    """The premise of the coverage gap. Pinned so the gap cannot silently close."""
    reachable = {
        resolve_effective_intelligence_mode(m, ["hubspot"])
        for m in ("fast", "standard", "reasoning", "agent")
    }

    assert reachable == {"fast", "agent"}


@pytest.mark.parametrize("requested_mode", ["standard", "reasoning", "agent"])
def test_connector_connected_orgs_are_not_validated_by_default(requested_mode: str) -> None:
    """Documents the open gap honestly rather than pretending it is closed."""
    effective = resolve_effective_intelligence_mode(requested_mode, ["hubspot"])

    assert effective == "agent"
    assert validation_enabled_for_mode(effective, _settings()) is False, (
        "If this now passes, someone added agent to the default validation set. "
        "That was measured live at 1e94e644 and reverted: +9.3s p50 and 3 of 3 "
        "answers replaced, because the validator judges tool-derived answers "
        "against unrelated RAG chunks. See docs/delivery/grounding-validator-"
        "latency.json before changing it — the fix is a tool-aware validator."
    )


def test_orgs_without_connectors_are_still_validated() -> None:
    """The validator is not dead: RAG-only orgs stay in standard/reasoning."""
    effective = resolve_effective_intelligence_mode("standard", [])

    assert effective == "standard"
    assert validation_enabled_for_mode(effective, _settings()) is True


def test_accuracy_priority_is_the_documented_opt_in() -> None:
    """A connector-connected org that wants validation has a real way to get it."""
    for mode in ("fast", "standard", "reasoning", "agent"):
        assert validation_enabled_for_mode(mode, _settings("accuracy_priority")) is True


def test_speed_priority_still_validates_agent() -> None:
    settings = _settings("speed_priority")

    assert validation_enabled_for_mode("agent", settings) is True
    assert validation_enabled_for_mode("standard", settings) is False


def test_master_switch_still_wins() -> None:
    off = IntelligenceEngineSettings(validation_enabled=False, performance_mode="balanced")

    for mode in ("fast", "standard", "reasoning", "agent"):
        assert validation_enabled_for_mode(mode, off) is False


@pytest.mark.asyncio
async def test_validator_rejects_answers_when_no_context_was_retrieved() -> None:
    """Why the call site also needs the has_context guard, independent of mode.

    With no retrieved context this validator returns is_valid=False, which the
    caller turns into regeneration and then SAFE_FALLBACK. Any mode that
    validates must therefore skip turns with no RAG sources, or it converts
    correct tool-derived answers into a "not enough reliable context" apology.
    """
    from app.services.answer_validator import validate_grounded_answer

    result = await validate_grounded_answer("The deal closes on March 3rd.", [])

    assert result["is_valid"] is False
    assert "no_retrieved_context" in result["issues"]
