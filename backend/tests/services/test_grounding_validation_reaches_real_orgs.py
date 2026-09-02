"""Who actually gets grounding validation, and how the coverage gap was closed.

This file previously asserted the opposite of what it asserts now, and the
history is the point.

The gap. resolve_effective_intelligence_mode upgrades BOTH standard and
reasoning to agent whenever a connector is connected, and leaves fast as fast.
A connector-connected org can therefore only ever reach {fast, agent}. While the
validation set was {standard, reasoning}, the intersection was empty: grounding
validation was unreachable for every org with a connector. Zero
`answer.grounding.validated` events across the whole measurement window agreed.

The first attempt to close it. Adding agent to the set was tried live at
1e94e644 and reverted the same day
(docs/delivery/grounding-validator-latency.json): p50 9309ms / p95 10131ms added
against a generation p50 of 3123ms, and 3 of 3 agent-mode answers replaced, one
falling through to SAFE_FALLBACK. The cause was structural — agent mode is where
answers come from TOOLS while RAG chunks are incidentally present, so a RAG-only
validator compared a tool-derived conclusion against unrelated knowledge chunks
and correctly found it unsupported.

The actual fix. The validator is now tool-aware: executed tool results are
first-class evidence, and the regeneration path sees the same evidence. Agent
mode is back in the default set because the instrument can finally judge those
turns. Tests for the validator itself live in
tests/services/test_tool_aware_grounding_validator.py, and the call-site wiring
in tests/operators/test_finalize_passes_tool_evidence.py.

What is pinned here is the composition — the thing that made the gap invisible
in the first place. Neither the mode-upgrade rule nor the validation set is
readable on its own; only their intersection tells you who is covered.
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
    """The premise of the whole gap. Pinned because it is deeply non-obvious."""
    reachable = {
        resolve_effective_intelligence_mode(m, ["hubspot"])
        for m in ("fast", "standard", "reasoning", "agent")
    }

    assert reachable == {"fast", "agent"}


@pytest.mark.parametrize("requested_mode", ["standard", "reasoning", "agent"])
def test_connector_connected_orgs_are_now_validated(requested_mode: str) -> None:
    """The gap, closed. This is the assertion that used to read `is False`."""
    effective = resolve_effective_intelligence_mode(requested_mode, ["hubspot"])

    assert effective == "agent"
    assert validation_enabled_for_mode(effective, _settings()) is True, (
        "If this fails, agent mode was removed from the default validation set "
        "and every connector-connected org silently lost grounding validation. "
        "Agent mode is only safe to validate while the validator is tool-aware "
        "(answer_validator.build_evidence) — if that was reverted, revert this "
        "together with it and say so, rather than leaving the set inconsistent."
    )


def test_orgs_without_connectors_are_still_validated() -> None:
    effective = resolve_effective_intelligence_mode("standard", [])

    assert effective == "standard"
    assert validation_enabled_for_mode(effective, _settings()) is True


def test_fast_mode_remains_unvalidated_by_default() -> None:
    """fast is the deliberate latency escape hatch; accuracy_priority opts in."""
    assert validation_enabled_for_mode("fast", _settings()) is False
    assert validation_enabled_for_mode("fast", _settings("accuracy_priority")) is True


def test_accuracy_priority_validates_everything() -> None:
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
async def test_validator_still_rejects_answers_with_no_evidence_at_all() -> None:
    """Tool-awareness widened what counts as evidence; it did not remove the floor.

    A turn with neither retrieved context nor tool results has nothing to be
    grounded against, and must still be rejected rather than waved through.
    """
    from app.services.answer_validator import validate_grounded_answer

    result = await validate_grounded_answer("The deal closes on March 3rd.", [])

    assert result["is_valid"] is False
    assert "no_retrieved_context" in result["issues"]


@pytest.mark.asyncio
async def test_a_tool_answering_turn_is_no_longer_treated_as_contextless() -> None:
    """The behavioural difference that justifies re-including agent mode."""
    from typing import Any

    from app.services import answer_validator

    class _Response:
        content = '{"is_valid": true, "issues": [], "confidence": 0.9, "requires_human": false}'

    class _Router:
        async def complete(self, **kwargs: Any):
            return _Response()

    original = answer_validator.get_model_router
    answer_validator.get_model_router = lambda: _Router()  # type: ignore[assignment]
    try:
        result = await answer_validator.validate_grounded_answer(
            "You have 3 open deals.",
            [],
            tool_calls=[
                {"tool": "hubspot_search_deals", "result": {"success": True, "deals": [1, 2, 3]}}
            ],
        )
    finally:
        answer_validator.get_model_router = original  # type: ignore[assignment]

    assert result["is_valid"] is True
    assert "no_retrieved_context" not in result["issues"]
