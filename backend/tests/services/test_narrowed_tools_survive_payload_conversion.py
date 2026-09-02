"""The narrowing proof must survive payload conversion, not just exist.

Root cause of the `unnarrowed_tool_attach_blocked` bursts of 2026-08-12 (10
events) and 08-13 (109 events), traced 2026-09-02.

`NarrowedTools` is a `list` subclass carrying `gravitre_narrowed = True`, and
`assert_tools_narrowed` checks for that attribute. Every ordinary way of copying
a list -- `list(x)`, a comprehension, a slice -- returns a plain `list` and
silently discards the marker. So the guard was never wrong; the plumbing kept
losing the evidence.

Two separate instances of the same mistake:

  1. `round_tools = list(attach_tools)` in the unified turn. Stripped the marker
     on EVERY tool-carrying turn, so `unified_turn.round_0` raised every time.
     Fixed 2026-08-13 at `65161f90` ("fix NarrowedTools round-trip in unified
     turn"), which is exactly the day the events stopped.

  2. `kwargs["tools"] = [openai_tool_payload(t) for t in round_tools]`, whose
     value is handed to `complete_with_tools` on the NON-OpenAI provider path,
     where narrowing is asserted a second time. This half was never fixed and
     accounts for the 8 events logged at
     `provider_tool_router.complete_with_tools`. It stayed quiet only because
     the deployment routes unified turns to OpenAI models, which take the
     streaming path and never call `complete_with_tools`. Any Anthropic or
     Gemini turn carrying tools would still have tripped it.

The guard itself was already well tested (see
`test_g5_unnarrowed_tool_attach_guard.py`). What no test covered was the
round-trip: that a value which passes the guard still passes it after being
converted for the provider. That omission is why a burst of 119 events was
needed to discover it, and why these tests exist.
"""
from __future__ import annotations

import json

import pytest

from app.services.narrowed_tools import (
    NarrowedTools,
    assert_tools_narrowed,
    mark_narrowed,
    openai_tool_payload,
)

TOOL = {
    "type": "function",
    "function": {"name": "hubspot_search_deals", "parameters": {"type": "object"}},
    # Retrieval metadata that must be stripped before reaching OpenAI.
    "invoke_action": "search",
    "integration": "hubspot",
}


def test_as_openai_tools_keeps_the_narrowing_proof() -> None:
    narrowed = mark_narrowed([TOOL], source="embedding_narrow_tools_for_turn")

    payload = narrowed.as_openai_tools()

    assert_tools_narrowed(payload, where="test")  # must not raise
    assert isinstance(payload, NarrowedTools)
    assert payload.source == "embedding_narrow_tools_for_turn"


def test_as_openai_tools_still_strips_provider_illegal_keys() -> None:
    """Preserving the marker must not stop the sanitising it exists to do."""
    payload = mark_narrowed([TOOL]).as_openai_tools()

    assert set(payload[0].keys()) == {"type", "function"}
    assert "invoke_action" not in payload[0]
    assert "integration" not in payload[0]


def test_payload_is_json_serialisable_as_a_plain_array() -> None:
    """A list subclass must not change what goes on the wire."""
    payload = mark_narrowed([TOOL]).as_openai_tools()

    encoded = json.dumps(payload)

    assert json.loads(encoded) == [openai_tool_payload(TOOL)]


def test_plain_comprehension_still_loses_the_marker() -> None:
    """Pins WHY this class of bug happens, so the reason is not forgotten.

    This is the shape that caused both instances. It is not a bug in itself --
    it is the trap. Any new code copying tools must use as_openai_tools or
    mark_narrowed rather than a bare comprehension.
    """
    narrowed = mark_narrowed([TOOL])

    stripped = [openai_tool_payload(t) for t in narrowed]

    assert not getattr(stripped, "gravitre_narrowed", False)
    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        assert_tools_narrowed(stripped, where="test")


def test_list_copy_still_loses_the_marker() -> None:
    """The exact expression from instance 1, kept as documentation."""
    narrowed = mark_narrowed([TOOL])

    copied = list(narrowed)

    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        assert_tools_narrowed(copied, where="test")


def test_mark_narrowed_does_not_double_wrap() -> None:
    narrowed = mark_narrowed([TOOL], source="a")

    again = mark_narrowed(narrowed, source="b")

    assert again is narrowed
    assert again.source == "b"


def test_guard_is_not_laundered_by_the_new_conversion() -> None:
    """The invariant must still be able to fail.

    The unified turn now carries the marker through the payload conversion,
    which is only safe because the guard runs BEFORE it. If a genuinely
    unnarrowed list could acquire the marker on the way to the provider, the
    whole invariant would be decorative.
    """
    plain = [dict(TOOL)]

    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        assert_tools_narrowed(plain, where="test")


def test_unified_turn_asserts_before_converting_the_payload() -> None:
    """Structural: order matters here and it is easy to reverse by accident."""
    import inspect

    from app.services import unified_turn_reasoning_service as svc

    src = inspect.getsource(svc.run_unified_turn_shadow)
    assert_at = src.find('where=f"unified_turn.round_{prog_round}"')
    convert_at = src.find('kwargs["tools"] = mark_narrowed(')

    assert assert_at != -1, "the round-level guard is gone"
    assert convert_at != -1, "the marker-preserving conversion is gone"
    assert assert_at < convert_at, (
        "the narrowing guard must run BEFORE the payload conversion; the "
        "conversion carries the proof forward and would otherwise launder an "
        "unnarrowed list into a narrowed-looking one"
    )


def test_empty_tools_never_trip_the_guard() -> None:
    """Conversational turns legitimately carry no tools."""
    assert_tools_narrowed([], where="test")
    assert_tools_narrowed(None, where="test")
    assert_tools_narrowed(mark_narrowed([]), where="test")
