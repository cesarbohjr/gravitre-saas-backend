"""The grounding validator must judge answers against tool results, not docs alone.

Why this exists. Agent mode was enabled for grounding validation on 2026-09-02
and measured live. It came back at p50 9,309ms added and 3 of 3 correct answers
replaced — one of them a real HubSpot search result declared unsupported because
five unrelated knowledge snippets did not mention it
(docs/delivery/grounding-validator-latency.json). The inclusion was reverted.

Root cause was not the gate or the mode: it was that the validator could only
see RAG chunks, while agent-mode answers are routinely derived from tools. Every
connector-connected org can only reach {fast, agent}, so those orgs got no
grounding validation at all.

These tests pin the fix: tool results are first-class evidence, the failure path
regenerates from that same evidence, and the checks that actually protect users
(fabricated success, invented entities) still fire.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.answer_validator import (
    EVIDENCE_DOC,
    EVIDENCE_TOOL,
    build_evidence,
    validate_grounded_answer,
)


def _tool_call(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool, "result": result}


# --------------------------------------------------------------------------
# build_evidence: the unit that makes tool results visible at all
# --------------------------------------------------------------------------


def test_tool_results_become_evidence() -> None:
    evidence = build_evidence(
        [],
        [_tool_call("hubspot_search_deals", {"success": True, "deals": [{"name": "Acme"}]})],
    )

    assert len(evidence) == 1
    assert evidence[0]["kind"] == EVIDENCE_TOOL
    assert evidence[0]["label"] == "hubspot_search_deals"
    assert "Acme" in evidence[0]["content"]
    assert "SUCCESS" in evidence[0]["content"]


def test_failed_tool_results_are_kept_as_evidence() -> None:
    """A failure must stay visible, or fabricated-success cannot be caught."""
    evidence = build_evidence(
        [],
        [_tool_call("hubspot_create_deal", {"success": False, "error": "403 forbidden"})],
    )

    assert len(evidence) == 1
    assert "FAILED" in evidence[0]["content"]
    assert "403 forbidden" in evidence[0]["content"]


def test_docs_and_tools_are_both_carried() -> None:
    evidence = build_evidence(
        [{"source": "handbook.pdf", "content": "Refund policy is 30 days."}],
        [_tool_call("gmail_search", {"success": True, "messages": []})],
    )

    kinds = sorted(item["kind"] for item in evidence)
    assert kinds == [EVIDENCE_DOC, EVIDENCE_TOOL]


def test_empty_and_malformed_rows_are_dropped() -> None:
    evidence = build_evidence(
        [{"source": "x", "content": "   "}, "not-a-dict"],  # type: ignore[list-item]
        [{"tool": "", "result": {}}, "also-not-a-dict"],  # type: ignore[list-item]
    )

    assert evidence == []


def test_large_tool_payloads_are_truncated_but_marked() -> None:
    big = {"success": True, "rows": [{"id": i, "name": f"deal-{i}"} for i in range(500)]}
    evidence = build_evidence([], [_tool_call("hubspot_search_deals", big)])

    content = evidence[0]["content"]
    assert "truncated" in content
    assert "deal-0" in content, "the head of the payload must survive truncation"


# --------------------------------------------------------------------------
# validate_grounded_answer: the behaviour that was wrong in production
# --------------------------------------------------------------------------


@pytest.fixture
def capture_model(monkeypatch):
    """Capture the prompt and force a deterministic verdict."""
    seen: dict[str, Any] = {}

    class _Response:
        content = '{"is_valid": true, "issues": [], "confidence": 0.9, "requires_human": false}'
        parsed = None

    class _Router:
        async def complete(self, **kwargs: Any):
            seen["prompt"] = kwargs.get("prompt")
            seen["called"] = seen.get("called", 0) + 1
            return _Response()

    monkeypatch.setattr(
        "app.services.answer_validator.get_model_router", lambda: _Router()
    )
    return seen


@pytest.mark.asyncio
async def test_tool_only_answer_is_validated_not_short_circuited(capture_model) -> None:
    """The exact production failure: no RAG, real tool result, correct answer."""
    result = await validate_grounded_answer(
        "You have 3 open deals: Acme, Globex and Initech.",
        [],  # no retrieved context at all
        tool_calls=[
            _tool_call(
                "hubspot_search_deals",
                {"success": True, "deals": [{"name": "Acme"}, {"name": "Globex"}, {"name": "Initech"}]},
            )
        ],
    )

    assert capture_model.get("called") == 1, "the model must actually be consulted"
    assert result["is_valid"] is True
    assert "no_retrieved_context" not in result["issues"]


@pytest.mark.asyncio
async def test_no_evidence_at_all_still_short_circuits(capture_model) -> None:
    """Genuinely ungrounded turns must still be caught, and cost nothing."""
    result = await validate_grounded_answer("The answer is 42.", [], tool_calls=[])

    assert capture_model.get("called") is None, "no model call when there is no evidence"
    assert result["is_valid"] is False
    assert "no_retrieved_context" in result["issues"]


@pytest.mark.asyncio
async def test_tool_results_are_presented_as_authoritative(capture_model) -> None:
    await validate_grounded_answer(
        "Acme is your largest open deal.",
        [],
        tool_calls=[_tool_call("hubspot_search_deals", {"success": True, "deals": [{"name": "Acme"}]})],
    )

    prompt = capture_model["prompt"]
    assert "[tool 1] hubspot_search_deals" in prompt
    assert "authoritative" in prompt.lower()
    assert "Acme" in prompt


@pytest.mark.asyncio
async def test_prompt_forbids_flagging_conversational_framing(capture_model) -> None:
    """A large share of the measured false rejections were framing, not claims."""
    await validate_grounded_answer(
        "Here's what I found. Want me to dig deeper?",
        [{"source": "doc", "content": "some content"}],
    )

    prompt = capture_model["prompt"].lower()
    assert "do not flag" in prompt
    assert "conversational framing" in prompt


@pytest.mark.asyncio
async def test_backwards_compatible_without_tool_calls(capture_model) -> None:
    """Existing RAG-only callers must be unaffected."""
    result = await validate_grounded_answer(
        "The refund policy is 30 days.",
        [{"source": "handbook.pdf", "content": "Refund policy is 30 days."}],
    )

    assert result["is_valid"] is True
    assert "[doc 1] handbook.pdf" in capture_model["prompt"]


@pytest.mark.asyncio
async def test_empty_answer_is_still_rejected_before_any_model_call(capture_model) -> None:
    result = await validate_grounded_answer(
        "   ", [], tool_calls=[_tool_call("t", {"success": True})]
    )

    assert capture_model.get("called") is None
    assert result["issues"] == ["empty_answer"]


@pytest.mark.asyncio
async def test_a_rejecting_model_still_rejects(monkeypatch) -> None:
    """The validator must not have been softened into always passing."""

    class _Response:
        content = (
            '{"is_valid": false, "issues": ["claimed success but tool FAILED"], '
            '"confidence": 0.95, "requires_human": true}'
        )
        parsed = None

    class _Router:
        async def complete(self, **kwargs: Any):
            return _Response()

    monkeypatch.setattr(
        "app.services.answer_validator.get_model_router", lambda: _Router()
    )

    result = await validate_grounded_answer(
        "Done — I created the deal for you.",
        [],
        tool_calls=[_tool_call("hubspot_create_deal", {"success": False, "error": "403"})],
    )

    assert result["is_valid"] is False
    assert result["requires_human"] is True
