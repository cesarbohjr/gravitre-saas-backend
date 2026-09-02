"""The grounding validator must be reachable by orgs that have connectors.

This was not a dormant call and not a routing gap. It was a composition bug
between two functions that each look correct alone:

  resolve_effective_intelligence_mode  upgrades standard AND reasoning -> agent
                                       whenever a connector is connected, and
                                       leaves fast as fast.
  validation_enabled_for_mode          default set was {standard, reasoning}.

So a connector-connected org can only ever reach {fast, agent}, and neither was
in the validation set: grounding validation was structurally unreachable for
every real customer, while staying enabled for modes they never run in. Zero
`answer.grounding.validated` events over the whole measurement window agreed.

The composition test is the one that matters here — asserting the default set
alone would not have caught this, because the set was defensible in isolation.
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


@pytest.mark.parametrize("requested_mode", ["standard", "reasoning", "agent"])
def test_connector_connected_org_gets_validation(requested_mode: str) -> None:
    """The actual regression: a real customer with a connector must be validated."""
    effective = resolve_effective_intelligence_mode(requested_mode, ["hubspot"])

    assert effective == "agent", "connectors should upgrade these modes to agent"
    assert validation_enabled_for_mode(effective, _settings()) is True, (
        "a connector-connected org cannot reach standard/reasoning, so excluding "
        "agent from the default set disables validation for every real customer"
    )


def test_only_fast_and_agent_are_reachable_with_connectors() -> None:
    """Pins the premise, so a future routing change cannot make the test vacuous."""
    reachable = {
        resolve_effective_intelligence_mode(m, ["hubspot"])
        for m in ("fast", "standard", "reasoning", "agent")
    }

    assert reachable == {"fast", "agent"}


def test_agent_is_in_the_default_validation_set() -> None:
    assert validation_enabled_for_mode("agent", _settings()) is True


def test_fast_still_opts_out_of_validation_by_default() -> None:
    """fast is deliberately honest about skipping heavy work; that is unchanged."""
    assert validation_enabled_for_mode("fast", _settings()) is False


def test_accuracy_priority_still_validates_everything() -> None:
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
    """Pins WHY agent mode also needs the has_context guard at the call site.

    With no retrieved context this validator returns is_valid=False, which the
    caller turns into regeneration and then SAFE_FALLBACK. Agent-mode turns often
    answer from tools with no RAG sources, so validating them without context
    would replace correct answers with a "not enough reliable context" apology.
    """
    from app.services.answer_validator import validate_grounded_answer

    result = await validate_grounded_answer("The deal closes on March 3rd.", [])

    assert result["is_valid"] is False
    assert "no_retrieved_context" in result["issues"]
