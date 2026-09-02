"""The call site must hand tool results to the validator AND to regeneration.

This is a deliberate guard against a failure this program hit four separate
times: a fix that is correct in the unit it touches, but wired one layer below
the path production actually takes. The tool-aware validator in
answer_validator.py is provably correct on its own; it is worthless if
_finalize_assistant_response keeps calling it with RAG chunks only.

Two wiring facts are pinned here:

  1. should_validate must become True for a tool-answering turn with zero RAG
     sources. Previously has_context = bool(rag_sources), so exactly those turns
     were skipped — and connector-connected orgs are mostly those turns.
  2. the regeneration path must receive the same tool evidence. Regenerating a
     tool-derived answer from unrelated documents would produce a fluent,
     confident, wrong answer, which is worse than the rejection it replaces.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import app.operators.agent_intelligence as ai


class _EngineSettings:
    confidence_threshold = 0.4


class _FakeClient:
    """Audit writes go through write_audit_event, which is patched; unused here."""


class _FakeReactResult:
    """Minimal stand-in for the ReAct result the finalize path consumes."""

    def __init__(self, tool_calls: list[Any]) -> None:
        self.tool_calls = tool_calls

    def to_dict(self) -> dict[str, Any]:
        return {"trace": [], "tool_calls": self.tool_calls}


@pytest.fixture
def finalize_env(monkeypatch):
    """Record everything the finalize path hands to its collaborators."""
    calls: dict[str, list[dict[str, Any]]] = {"validate": [], "regen": [], "audit": []}

    async def _fake_validate(answer, retrieved_context, **kwargs):
        calls["validate"].append(
            {
                "answer": answer,
                "rag": retrieved_context,
                "tool_calls": kwargs.get("tool_calls"),
            }
        )
        return {
            "is_valid": True,
            "issues": [],
            "requires_human": False,
            "confidence": 0.9,
            "confidence_source": "model",
        }

    def _fake_audit(client, **kwargs):
        calls["audit"].append(kwargs)

    monkeypatch.setattr(ai, "validate_grounded_answer", _fake_validate)
    monkeypatch.setattr(ai, "write_audit_event", _fake_audit)
    monkeypatch.setattr(ai, "validation_enabled_for_mode", lambda *a, **k: True)
    return calls


def _operator() -> ai.AgentIntelligence:
    return ai.AgentIntelligence.__new__(ai.AgentIntelligence)


async def _finalize(op, *, rag_sources, tool_calls, answer="You have 3 open deals."):
    return await op._finalize_assistant_response(
        settings=SimpleNamespace(),
        org_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        mode_key="agent",
        query="how many open deals do I have",
        answer=answer,
        rag_sources=rag_sources,
        react_result=_FakeReactResult(tool_calls),
        engine_settings=_EngineSettings(),
        message_id=None,
        client=_FakeClient(),
        conflicts=None,
        refined_query=None,
    )


@pytest.mark.asyncio
async def test_tool_answering_turn_with_no_rag_is_validated(finalize_env) -> None:
    """The production case: connector answer, zero documents."""
    tool_calls = [
        {"tool": "hubspot_search_deals", "result": {"success": True, "deals": [1, 2, 3]}}
    ]

    await _finalize(_operator(), rag_sources=[], tool_calls=tool_calls)

    assert len(finalize_env["validate"]) == 1, (
        "a tool-answering turn must be validated, not skipped as contextless"
    )
    assert finalize_env["validate"][0]["tool_calls"] == tool_calls


@pytest.mark.asyncio
async def test_turn_with_neither_evidence_is_still_skipped(finalize_env) -> None:
    await _finalize(_operator(), rag_sources=[], tool_calls=[])

    assert finalize_env["validate"] == []
    skip_rows = [row for row in finalize_env["audit"] if row["metadata"].get("skipped")]
    assert len(skip_rows) == 1
    assert skip_rows[0]["metadata"]["skipReason"] == "no_evidence"


@pytest.mark.asyncio
async def test_audit_records_which_evidence_carried_the_turn(finalize_env) -> None:
    await _finalize(
        _operator(),
        rag_sources=[],
        tool_calls=[{"tool": "hubspot_search_deals", "result": {"success": True}}],
    )

    verdicts = [r for r in finalize_env["audit"] if not r["metadata"].get("skipped")]
    assert len(verdicts) == 1
    md = verdicts[0]["metadata"]
    assert md["evidenceKind"] == "tool"
    assert md["toolResultCount"] == 1
    assert md["ragSourceCount"] == 0


@pytest.mark.asyncio
async def test_mixed_evidence_is_labelled(finalize_env) -> None:
    await _finalize(
        _operator(),
        rag_sources=[{"source": "handbook.pdf", "content": "policy"}],
        tool_calls=[{"tool": "gmail_search", "result": {"success": True}}],
    )

    verdicts = [r for r in finalize_env["audit"] if not r["metadata"].get("skipped")]
    assert verdicts[0]["metadata"]["evidenceKind"] == "tool+doc"


@pytest.mark.asyncio
async def test_regeneration_receives_the_same_tool_evidence(monkeypatch) -> None:
    """The half of the fix that is easiest to forget and worst to get wrong."""
    regen_kwargs: dict[str, Any] = {}
    verdicts = iter([False, True])

    async def _fake_validate(answer, retrieved_context, **kwargs):
        return {
            "is_valid": next(verdicts, True),
            "issues": [],
            "requires_human": False,
            "confidence": 0.9,
            "confidence_source": "model",
        }

    async def _fake_regen(self, **kwargs):
        regen_kwargs.update(kwargs)
        return "Regenerated: you have 3 open deals."

    monkeypatch.setattr(ai, "validate_grounded_answer", _fake_validate)
    monkeypatch.setattr(ai, "write_audit_event", lambda client, **k: None)
    monkeypatch.setattr(ai, "validation_enabled_for_mode", lambda *a, **k: True)
    monkeypatch.setattr(
        ai.AgentIntelligence, "_regenerate_grounded_answer", _fake_regen
    )

    tool_calls = [{"tool": "hubspot_search_deals", "result": {"success": True}}]
    await _finalize(_operator(), rag_sources=[], tool_calls=tool_calls)

    assert regen_kwargs.get("tool_calls") == tool_calls, (
        "regenerating from RAG alone would delete the tool's findings"
    )


@pytest.mark.asyncio
async def test_malformed_tool_calls_do_not_crash_the_turn(finalize_env) -> None:
    await _finalize(
        _operator(),
        rag_sources=[{"source": "d", "content": "c"}],
        tool_calls=["not-a-dict", None],  # type: ignore[list-item]
    )

    assert finalize_env["validate"][0]["tool_calls"] == []


@pytest.mark.asyncio
async def test_missing_react_result_does_not_crash(monkeypatch, finalize_env) -> None:
    op = _operator()
    result = await op._finalize_assistant_response(
        settings=SimpleNamespace(),
        org_id="11111111-1111-4111-8111-111111111111",
        user_id="22222222-2222-4222-8222-222222222222",
        mode_key="agent",
        query="q",
        answer="a",
        rag_sources=[{"source": "d", "content": "c"}],
        react_result=None,
        engine_settings=_EngineSettings(),
        message_id=None,
        client=_FakeClient(),
        conflicts=None,
        refined_query=None,
    )

    assert result is not None
    assert finalize_env["validate"][0]["tool_calls"] == []


@pytest.mark.asyncio
async def test_regeneration_prompt_actually_contains_the_tool_data(monkeypatch) -> None:
    """Behavioural, not structural.

    A structural check for `build_evidence` and `tool_calls` in the source passes
    even if the body calls build_evidence(rag_sources, None) and silently throws
    the tool evidence away. Mutation testing found exactly that blind spot, so
    this asserts on the prompt the model really receives.
    """
    seen: dict[str, Any] = {}

    class _Response:
        content = "Regenerated answer."

    class _Router:
        async def complete(self, **kwargs: Any):
            seen.update(kwargs)
            return _Response()

    monkeypatch.setattr("app.services.model_router.get_model_router", lambda: _Router())

    out = await _operator()._regenerate_grounded_answer(
        settings=SimpleNamespace(),
        org_id="11111111-1111-4111-8111-111111111111",
        query="how many open deals",
        draft="You have 3 open deals.",
        rag_sources=[],
        tool_calls=[
            {
                "tool": "hubspot_search_deals",
                "result": {"success": True, "deals": [{"name": "Acme Corp"}]},
            }
        ],
    )

    prompt = seen["prompt"]
    assert out == "Regenerated answer."
    assert "hubspot_search_deals" in prompt, "the tool must be named in the prompt"
    assert "Acme Corp" in prompt, "the tool's actual data must reach the model"
    assert "[tool]" in prompt, "tool evidence must be distinguishable from documents"
    assert "authoritative" in prompt.lower()


@pytest.mark.asyncio
async def test_regeneration_still_works_with_documents_only(monkeypatch) -> None:
    """The pre-existing RAG-only behaviour must not regress."""
    seen: dict[str, Any] = {}

    class _Response:
        content = "Regenerated from docs."

    class _Router:
        async def complete(self, **kwargs: Any):
            seen.update(kwargs)
            return _Response()

    monkeypatch.setattr("app.services.model_router.get_model_router", lambda: _Router())

    await _operator()._regenerate_grounded_answer(
        settings=SimpleNamespace(),
        org_id="11111111-1111-4111-8111-111111111111",
        query="refund policy",
        draft="30 days.",
        rag_sources=[{"source": "handbook.pdf", "content": "Refunds within 30 days."}],
    )

    assert "handbook.pdf" in seen["prompt"]
    assert "[doc]" in seen["prompt"]
