"""Questions a public web search cannot help with must not start one.

Replayed 2026-10-11: with nothing in the org's knowledge base, the evidence
loop escalated "What time is it?", "What's 2 plus 2?", "What did I just ask
you?", "What's on my calendar today?" and "How did the website do last week?"
to a live web search on both surfaces, adding seconds and sending private
questions to a search engine. A question with a recency cue still searches.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.services.adaptive_research_cascade import answerable_without_web
from tests.scenarios.conversation_harness import ScenarioHarness

NO_WEB = (
    "What's 2 plus 2?",
    "What did I just ask you?",
    "Can you help me with my email?",
    "What time is it?",
    "Explain what a conversion is.",
    "What's on my calendar today?",
    "How did the website do last week?",
)


async def _searches_for(surface: str, message: str) -> int:
    searches: list[Any] = []

    async def _fake_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
        searches.append((args, kwargs))
        return {"results": []}

    with ScenarioHarness() as h, patch("app.services.web_research.search_web", _fake_search):
        h.connected.extend(["gmail", "google_analytics"])
        conv = h.conversation(surface)
        await conv.say("Hi", "Hi! What can I help with?")
        await conv.say(message, "Sure.")
    return len(searches)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["text", "voice"])
@pytest.mark.parametrize("message", NO_WEB)
async def test_no_web_search_for_questions_it_cannot_help(surface: str, message: str) -> None:
    assert await _searches_for(surface, message) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["text", "voice"])
async def test_a_news_question_still_searches(surface: str) -> None:
    assert await _searches_for(surface, "What's the latest news about OpenAI?") >= 1


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        *[(m, True) for m in NO_WEB],
        ("What's the latest news about OpenAI?", False),
        ("What is Acme Corp?", False),
        ("Compare HubSpot and Salesforce pricing", False),
        ("What are good B2B email subject lines?", False),
        ("How did my campaigns do this week?", True),
    ],
)
def test_answerable_without_web(message: str, expected: bool) -> None:
    assert answerable_without_web(message) is expected
