"""Site 7 regression: `rewrite_for_retrieval` must actually reach the model router.

The pre-existing test for this function
(`test_intelligence_engine_gaps.py::test_query_rewriter_uses_conversation_context`)
passes whether or not the dormancy bug is present, because it patches the
factory with a bare MagicMock, which accepts any signature while the real
zero-arg `get_model_router` raises TypeError. Demonstrated in
`backend/scripts/scratch_prove_existing_rewriter_test_blind.py`.

Every fake here therefore enforces the real arity, so a reintroduced
`get_model_router(settings)` fails loudly instead of being absorbed by the mock
and then swallowed by the handler.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import query_rewriter as qr

HISTORY = [
    {"role": "user", "content": "Tell me about the Acme Corp account"},
    {"role": "assistant", "content": "Acme Corp is an enterprise customer on the Platinum plan."},
]
FOLLOW_UP = "and what about their renewal?"


class _StrictRouter:
    def __init__(self, content: str, calls: list[dict[str, Any]]) -> None:
        self._content = content
        self._calls = calls

    async def complete(self, **kwargs: Any) -> SimpleNamespace:
        self._calls.append(kwargs)
        return SimpleNamespace(content=self._content)


@pytest.fixture
def routed(monkeypatch):
    """Install a factory that enforces the real zero-argument signature."""

    def _install(content: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def _factory(*args: Any, **kwargs: Any):
            assert not args and not kwargs, (
                "get_model_router takes no arguments; passing one is the dormancy "
                f"bug this test exists to catch. got args={args!r} kwargs={kwargs!r}"
            )
            return _StrictRouter(content, calls)

        monkeypatch.setattr(qr, "get_model_router", _factory)
        return calls

    return _install


@pytest.mark.asyncio
async def test_follow_up_is_rewritten_into_a_standalone_query(routed):
    """The regression itself: dormant, this returned the pronoun unchanged."""
    routed('{"refined_query": "Acme Corp renewal date and terms"}')
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert out["original_query"] == FOLLOW_UP
    assert out["refined_query"] == "Acme Corp renewal date and terms"


@pytest.mark.asyncio
async def test_settings_argument_does_not_reach_the_factory(routed):
    """The caller passes settings; it must not be forwarded to the factory."""
    routed('{"refined_query": "Acme Corp renewal date"}')
    out = await qr.rewrite_for_retrieval(
        FOLLOW_UP, HISTORY, org_id="org-1", settings=object()
    )
    assert out["refined_query"] == "Acme Corp renewal date"


@pytest.mark.asyncio
async def test_conversation_context_is_sent_to_the_model(routed):
    """Without the history the model cannot resolve 'their'."""
    calls = routed('{"refined_query": "Acme Corp renewal"}')
    await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert calls, "the model should have been consulted"
    prompt = calls[0]["prompt"]
    assert "Acme Corp" in prompt
    assert FOLLOW_UP in prompt


@pytest.mark.asyncio
async def test_uses_the_cheap_intent_tier(routed):
    """This runs on every non-fast turn; it must not silently become expensive."""
    from app.services.model_router import TaskType

    calls = routed('{"refined_query": "Acme Corp renewal"}')
    await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert calls[0]["task_type"] is TaskType.INTENT_DETECTION
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["max_tokens"] <= 512


@pytest.mark.asyncio
async def test_org_id_is_propagated_for_attribution(routed):
    calls = routed('{"refined_query": "Acme Corp renewal"}')
    await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-42")
    assert calls[0]["org_id"] == "org-42"


@pytest.mark.asyncio
async def test_no_history_skips_the_model_entirely(routed):
    """Nothing to resolve against, so spending a model call would be waste."""
    calls = routed('{"refined_query": "should not be used"}')
    out = await qr.rewrite_for_retrieval("pipeline status", None, org_id="org-1")
    assert out["refined_query"] == "pipeline status"
    assert calls == []


@pytest.mark.asyncio
async def test_history_without_usable_turns_skips_the_model(routed):
    calls = routed('{"refined_query": "should not be used"}')
    out = await qr.rewrite_for_retrieval(
        "pipeline status", [{"role": "system", "content": "be nice"}], org_id="org-1"
    )
    assert out["refined_query"] == "pipeline status"
    assert calls == []


@pytest.mark.asyncio
async def test_empty_query_returns_empty_without_calling(routed):
    calls = routed('{"refined_query": "x"}')
    out = await qr.rewrite_for_retrieval("   ", HISTORY, org_id="org-1")
    assert out["original_query"] == ""
    assert out["refined_query"] == ""
    assert calls == []


@pytest.mark.asyncio
async def test_model_echoing_the_query_falls_back_to_original(routed):
    """A no-op rewrite must not be presented as a rewrite."""
    routed(f'{{"refined_query": "{FOLLOW_UP}"}}')
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert out["refined_query"] == FOLLOW_UP


@pytest.mark.asyncio
async def test_unparseable_model_output_falls_back_to_original(routed):
    routed("I cannot help with that.")
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert out["refined_query"] == FOLLOW_UP


@pytest.mark.asyncio
async def test_refined_query_is_length_capped(routed):
    routed('{"refined_query": "' + "a" * 5000 + '"}')
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert len(out["refined_query"]) == 2000


@pytest.mark.asyncio
async def test_model_ran_flag_distinguishes_dormant_from_declined(routed):
    """A dormant call and a model that declines both return the query unchanged.

    `model_ran` is the only thing that separates them, and it is what the
    production audit event reports, so it has to be right in every branch.
    """
    routed('{"refined_query": "Acme Corp renewal date"}')
    changed = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert changed["model_ran"] is True
    assert changed["refined_query"] != FOLLOW_UP

    routed(f'{{"refined_query": "{FOLLOW_UP}"}}')
    declined = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert declined["model_ran"] is True, "the model ran; it simply declined to rewrite"
    assert declined["refined_query"] == FOLLOW_UP

    routed("not json at all")
    unparseable = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert unparseable["model_ran"] is True

    skipped = await qr.rewrite_for_retrieval("pipeline status", None, org_id="org-1")
    assert skipped["model_ran"] is False, "no history, so the model was never asked"


@pytest.mark.asyncio
async def test_model_ran_is_false_when_the_call_fails(monkeypatch):
    """The dormancy signature itself: the factory blows up before completing."""

    def _boom(*args: Any, **kwargs: Any):
        raise TypeError("get_model_router() takes 0 positional arguments but 1 was given")

    monkeypatch.setattr(qr, "get_model_router", _boom)
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert out["model_ran"] is False
    assert out["refined_query"] == FOLLOW_UP


@pytest.mark.asyncio
async def test_provider_outage_degrades_to_the_original_query(monkeypatch):
    """Graceful degradation must survive — retrieval still gets a usable query."""

    def _boom(*args: Any, **kwargs: Any):
        raise RuntimeError("all providers unavailable")

    monkeypatch.setattr(qr, "get_model_router", _boom)
    out = await qr.rewrite_for_retrieval(FOLLOW_UP, HISTORY, org_id="org-1")
    assert out["original_query"] == FOLLOW_UP
    assert out["refined_query"] == FOLLOW_UP
