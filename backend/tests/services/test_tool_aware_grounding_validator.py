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
    big = {"success": True, "rows": [{"id": i, "name": f"deal-{i}"} for i in range(5000)]}
    evidence = build_evidence([], [_tool_call("hubspot_search_deals", big)])

    content = evidence[0]["content"]
    assert "[TRUNCATED" in content
    assert "deal-0" in content, "the head of the payload must survive truncation"


def test_a_ten_record_listing_is_not_truncated() -> None:
    """The exact payload shape that caused the one false rejection at 742414b9.

    "list my hubspot contacts" returned ten contacts and the answer enumerated
    all ten. At the old 2000-char budget the tail was cut, so the validator
    could not see the records the answer named and rejected it. The budget must
    comfortably hold a realistic ten-record listing.
    """
    contacts = [
        {
            "id": f"{i}",
            "firstname": f"Contact{i}",
            "lastname": "Smoketest",
            "email": f"contact{i}@example-company-with-a-long-domain.com",
            "company": "Example Company LLC",
            "createdate": "2026-08-01T12:00:00Z",
        }
        for i in range(10)
    ]
    evidence = build_evidence(
        [], [_tool_call("hubspot_list_contacts", {"success": True, "contacts": contacts})]
    )

    content = evidence[0]["content"]
    assert "[TRUNCATED" not in content, "a ten-record listing must fit in the budget"
    assert "Contact9" in content, "the last record must be visible to the validator"


@pytest.mark.asyncio
async def test_prompt_tells_the_model_how_to_treat_truncation(capture_model) -> None:
    """Absent evidence is incomplete, not contradictory."""
    big = {"success": True, "rows": [{"id": i, "v": "x" * 50} for i in range(5000)]}
    await validate_grounded_answer(
        "Here are your records.", [], tool_calls=[_tool_call("t", big)]
    )

    prompt = capture_model["prompt"]
    assert "TRUNCATION" in prompt
    assert "incomplete, not contradictory" in prompt


@pytest.mark.asyncio
async def test_truncation_is_reported_in_the_result(capture_model) -> None:
    big = {"success": True, "rows": [{"id": i, "v": "x" * 50} for i in range(5000)]}

    truncated = await validate_grounded_answer(
        "Here are your records.", [], tool_calls=[_tool_call("t", big)]
    )
    small = await validate_grounded_answer(
        "You have 1 deal.", [], tool_calls=[_tool_call("t", {"success": True, "n": 1})]
    )

    assert truncated["evidence_truncated"] is True
    assert small["evidence_truncated"] is False


def test_total_tool_budget_caps_a_multi_tool_turn() -> None:
    """Per-tool budget alone would let eight big results balloon the prompt."""
    from app.services.answer_validator import _evidence_block

    calls = [
        _tool_call(f"tool_{i}", {"success": True, "rows": [{"v": "x" * 100}] * 200})
        for i in range(8)
    ]
    block = _evidence_block(build_evidence([], calls))

    assert len(block) < 20000, f"evidence block ballooned to {len(block)} chars"
    assert "tool_0" in block, "the first tool must still be fully represented"


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


# --------------------------------------------------------------------------
# fail-open must be visible: assessorRan=false with no reason is unreadable
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_error_is_named_in_the_fallthrough(monkeypatch) -> None:
    class _Router:
        async def complete(self, **kwargs: Any):
            raise RuntimeError("All AI providers failed")

    monkeypatch.setattr(
        "app.services.answer_validator.get_model_router", lambda: _Router()
    )

    result = await validate_grounded_answer(
        "You have 3 open deals.", [{"source": "d", "content": "c"}]
    )

    assert result["is_valid"] is True, "must fail open, not apologise to the user"
    assert result["confidence_source"] == "heuristic"
    assert result["validator_fallthrough"] == "model_error:RuntimeError"


@pytest.mark.asyncio
async def test_unparseable_response_is_named_in_the_fallthrough(monkeypatch) -> None:
    class _Response:
        content = "Sure! Here is my assessment: the answer looks fine to me."

    class _Router:
        async def complete(self, **kwargs: Any):
            return _Response()

    monkeypatch.setattr(
        "app.services.answer_validator.get_model_router", lambda: _Router()
    )

    result = await validate_grounded_answer(
        "You have 3 open deals.", [{"source": "d", "content": "c"}]
    )

    assert result["validator_fallthrough"] == "no_json_in_response"


@pytest.mark.asyncio
async def test_empty_response_is_distinguished_from_unparseable(monkeypatch) -> None:
    class _Response:
        content = "   "

    class _Router:
        async def complete(self, **kwargs: Any):
            return _Response()

    monkeypatch.setattr(
        "app.services.answer_validator.get_model_router", lambda: _Router()
    )

    result = await validate_grounded_answer(
        "You have 3 open deals.", [{"source": "d", "content": "c"}]
    )

    assert result["validator_fallthrough"] == "empty_response"


@pytest.mark.asyncio
async def test_a_real_verdict_reports_no_fallthrough(capture_model) -> None:
    result = await validate_grounded_answer(
        "You have 3 open deals.", [{"source": "d", "content": "c"}]
    )

    from app.services.confidence_honesty import CONFIDENCE_SOURCE_MODEL

    assert result["confidence_source"] == CONFIDENCE_SOURCE_MODEL
    assert result["validator_fallthrough"] is None


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
