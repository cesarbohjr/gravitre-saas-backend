"""Standing battery: meta/capability questions never trigger external retrieval.

Mirrors withhold_no_tool discipline — combined pass rate must stay at 100%.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.adaptive_research_cascade import (
    filter_relevant_internet_results,
    normalize_internet_results,
    score_internet_result_relevance,
)
from app.services.conversational_reply_service import re_search_meta
from app.services.conversational_turn_gate import heuristic_turn_shape
from app.services.unified_turn_knowledge_context import should_augment_unified_turn_with_knowledge
from app.services.unified_turn_reasoning_service import apply_unified_turn_live


META_PHRASES = [
    "What can you help me with?",
    "what can you do?",
    "what are you able to do?",
    "what tools do you have access to?",
    "how can you help me?",
    "who are you?",
]

DOMAIN_PHRASES = [
    "What can you help with for our SEO campaign this quarter?",
    "best practices for HubSpot deal stages",
    "how should we prioritize product pages vs blog posts",
]


@pytest.mark.parametrize("message", META_PHRASES)
def test_meta_phrases_classified_and_skip_knowledge_augment(message: str) -> None:
    assert re_search_meta(message) is True
    assert should_augment_unified_turn_with_knowledge(message) is False
    decision = heuristic_turn_shape(message)
    assert decision is not None
    assert decision.shape == "conversational"
    assert decision.category == "meta_capability"


@pytest.mark.parametrize("message", DOMAIN_PHRASES)
def test_domain_phrases_not_suppressed_as_meta(message: str) -> None:
    assert re_search_meta(message) is False
    # Domain questions may still augment knowledge — must not be blocked as meta.
    assert should_augment_unified_turn_with_knowledge(
        message, classification={"department": "marketing"}
    ) is True


@pytest.mark.parametrize("message", META_PHRASES)
@pytest.mark.asyncio
async def test_live_meta_short_circuit_skips_shadow_and_research(message: str) -> None:
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    meta_text = (
        "I am Gravitre — a calm operator for your Connected tools. "
        "Connected for this org right now: HubSpot."
    )
    with patch(
        "app.services.conversational_reply_service.generate_conversational_reply",
        new=AsyncMock(return_value=meta_text),
    ), patch(
        "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
        new=AsyncMock(),
    ) as mock_shadow, patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new=AsyncMock(),
    ) as mock_knowledge:
        out = await apply_unified_turn_live(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            message=message,
            task_state={},
            conversation_history=[],
            connected_integrations=["hubspot"],
            settings=settings,
        )
    mock_shadow.assert_not_called()
    mock_knowledge.assert_not_called()
    assert out is not None
    assert "Connected" in out["message"] or "HubSpot" in out["message"]


def test_relevance_floor_drops_adversarial_noise() -> None:
    query = "What can you help me with?"
    noise = [
        {
            "title": "Usher - Yeah! (Official Music Video)",
            "url": "https://youtube.com/watch?v=noise",
            "snippet": "Watch Usher perform Yeah! Help me find the lyrics.",
        },
        {
            "title": "Google Assistant help",
            "url": "https://support.google.com/assistant",
            "snippet": "What can Google Assistant help me with today?",
        },
        {
            "title": "ESL: Can you help me?",
            "url": "https://esl.example/can-you-help",
            "snippet": "English phrases for asking for help.",
        },
    ]
    kept = filter_relevant_internet_results(query, noise)
    assert kept == []
    rows = normalize_internet_results(
        {"results": noise, "provider": "serper", "query": query},
        query=query,
    )
    assert rows == []


def test_relevance_floor_keeps_topical_seo_hit() -> None:
    query = "HubSpot SEO product page optimization best practices"
    hits = [
        {
            "title": "HubSpot SEO product page checklist",
            "url": "https://blog.hubspot.com/seo-product-pages",
            "snippet": "Optimize product page SEO titles, CTAs, and internal links in HubSpot.",
        },
        {
            "title": "Usher tour dates",
            "url": "https://example.com/usher",
            "snippet": "Concert tickets and help with seating.",
        },
    ]
    kept = filter_relevant_internet_results(query, hits)
    assert len(kept) == 1
    assert "HubSpot" in kept[0]["title"]
    assert score_internet_result_relevance(
        query, title=hits[0]["title"], snippet=hits[0]["snippet"]
    ) >= 0.22


def test_meta_capability_battery_combined_pass_rate() -> None:
    """Standing gate: every meta phrase + relevance adversarial case must pass."""
    failures: list[str] = []
    for message in META_PHRASES:
        if not re_search_meta(message):
            failures.append(f"meta_detect:{message}")
        if should_augment_unified_turn_with_knowledge(message):
            failures.append(f"augment:{message}")
    for message in DOMAIN_PHRASES:
        if re_search_meta(message):
            failures.append(f"over_suppress:{message}")
    noise_kept = filter_relevant_internet_results(
        "What can you help me with?",
        [
            {
                "title": "Usher - Yeah!",
                "url": "https://y.example/1",
                "snippet": "help me find the song",
            }
        ],
    )
    if noise_kept:
        failures.append("relevance_floor:noise")
    assert failures == [], f"meta_capability battery failures: {failures}"
