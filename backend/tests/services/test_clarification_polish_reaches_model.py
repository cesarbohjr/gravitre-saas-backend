"""Site 11 regression: `_polish_question` must actually reach the model router.

`get_model_router(self.settings)` raised TypeError on every call and the handler
swallowed it, so `_polish_question` always returned None and
`generate_clarification_question` fell back to `polished or question` — the raw
template. Every clarifying question the platform asked was therefore the
unpolished template string, which is a legitimate question and reads fine, so
nothing ever looked broken.

Unlike the other sites this one needs no audit instrument to prove live: the
polished question IS the user-visible output, so a live reply that differs from
the known template is direct evidence the model ran.

The fake enforces the real zero-argument signature, so a reintroduced
`get_model_router(self.settings)` fails loudly rather than being absorbed.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.clarification_engine import ClarificationEngine

DRAFT = "Which HubSpot deal did you mean and what should change about it?"
POLISHED = "Which HubSpot deal should I update, and what needs changing?"


@pytest.fixture
def engine() -> ClarificationEngine:
    return ClarificationEngine(SimpleNamespace(placeholder=True))


@pytest.fixture
def routed(monkeypatch):
    def _install(content: str | None, *, raises: BaseException | None = None):
        calls: list[dict[str, Any]] = []

        class _Router:
            async def complete(self, **kwargs: Any) -> SimpleNamespace:
                calls.append(kwargs)
                if raises is not None:
                    raise raises
                return SimpleNamespace(content=content)

        def _factory(*args: Any, **kwargs: Any):
            assert not args and not kwargs, (
                "get_model_router takes no arguments; passing one is the dormancy "
                f"bug this test exists to catch. got args={args!r} kwargs={kwargs!r}"
            )
            return _Router()

        monkeypatch.setattr("app.services.model_router.get_model_router", _factory)
        return calls

    return _install


@pytest.mark.asyncio
async def test_polish_calls_the_model_with_zero_arguments(engine, routed):
    calls = routed(POLISHED)

    result = await engine._polish_question(DRAFT)

    assert len(calls) == 1, "the model tier never ran — the call is still dormant"
    assert result == POLISHED


@pytest.mark.asyncio
async def test_draft_reaches_the_prompt(engine, routed):
    calls = routed(POLISHED)

    await engine._polish_question(DRAFT)

    assert DRAFT in calls[0]["prompt"]


@pytest.mark.asyncio
async def test_generated_question_uses_the_polished_text(engine, routed):
    """The whole point: the user must see the rewrite, not the template."""
    routed(POLISHED)

    question = await engine.generate_clarification_question(
        "under_specified_action",
        {},
        {},
        [],
        {"action": "update the deal", "specific_question": "Which one?"},
    )

    assert question == POLISHED


@pytest.mark.asyncio
async def test_empty_model_output_falls_back_to_the_draft(engine, routed):
    routed("   ")

    assert await engine._polish_question(DRAFT) is None


@pytest.mark.asyncio
async def test_model_failure_degrades_to_the_template(engine, routed):
    """Graceful degradation stays: a provider outage must not break clarification."""
    routed(None, raises=RuntimeError("provider down"))

    assert await engine._polish_question(DRAFT) is None


@pytest.mark.asyncio
async def test_high_risk_confirmation_is_never_polished(engine, monkeypatch):
    """High-risk confirmation copy is deliberate and must reach the user verbatim.

    Asserting from inside the fake would be blind: `_polish_question` catches
    bare `Exception`, and AssertionError is an Exception, so a raise there is
    swallowed and the template is returned anyway — the test would pass with the
    guard removed. Mutation testing caught exactly that. Count instead, and
    assert out here where nothing can swallow it.
    """
    calls: list[str] = []

    class _Router:
        async def complete(self, **kwargs: Any) -> SimpleNamespace:
            calls.append("called")
            return SimpleNamespace(content="a model-rewritten confirmation")

    monkeypatch.setattr(
        "app.services.model_router.get_model_router", lambda *a, **k: _Router()
    )
    monkeypatch.setattr(
        ClarificationEngine,
        "CLARIFICATION_TRIGGERS",
        {
            "high_risk_confirmation": {
                "question_template": (
                    "This will permanently delete the production record. "
                    "Confirm you want to proceed?"
                )
            }
        },
        raising=False,
    )

    question = await engine.generate_clarification_question(
        "high_risk_confirmation",
        {},
        {},
        [],
        {},
    )

    assert calls == [], "high-risk confirmation copy must not be rewritten by a model"
    assert question.startswith("This will permanently delete")


@pytest.mark.asyncio
async def test_short_questions_skip_the_model(engine, monkeypatch):
    """Cost guard: the <=20 char gate must keep short questions off the model."""
    calls: list[str] = []

    class _Router:
        async def complete(self, **kwargs: Any) -> SimpleNamespace:
            calls.append("called")
            return SimpleNamespace(content="rewritten")

    monkeypatch.setattr(
        "app.services.model_router.get_model_router", lambda *a, **k: _Router()
    )
    monkeypatch.setattr(
        ClarificationEngine,
        "CLARIFICATION_TRIGGERS",
        {"tiny": {"question_template": "Which one?"}},
        raising=False,
    )

    question = await engine.generate_clarification_question("tiny", {}, {}, [], {})

    assert question == "Which one?"
    assert calls == [], "a 10-character question should not pay for a model call"


@pytest.mark.asyncio
async def test_polished_output_is_returned_stripped(engine, routed):
    routed(f"  {POLISHED}\n")

    assert await engine._polish_question(DRAFT) == POLISHED
