"""Tests for unified-turn knowledge prefetch."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.unified_turn_knowledge_context import (
    build_unified_turn_knowledge_context,
    should_augment_unified_turn_with_knowledge,
)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("hello", False),
        ("thanks!", False),
        ("tell me about the best CRM practices for our team", True),
        ("What is NIST CSF Govern function?", True),
        ("ok", False),
    ],
)
def test_should_augment_informational_messages(message: str, expected: bool) -> None:
    assert (
        should_augment_unified_turn_with_knowledge(
            message,
            classification={"department": "all"},
        )
        is expected
    )


def test_skips_action_classification() -> None:
    assert (
        should_augment_unified_turn_with_knowledge(
            "tell me about the best approach",
            classification={"requires_action": True},
        )
        is False
    )


@pytest.mark.asyncio
async def test_auto_internet_when_internal_thin():
    settings = type(
        "S",
        (),
        {
            "internet_research_enabled": True,
            "tavily_api_key": "tvly-test",
            "gemini_api_key": "",
            "web_research_provider": "tavily",
            "web_research_fallback_tavily": True,
            "google_genai_use_vertexai": False,
            "google_cloud_project": "",
            "google_cloud_location": "us-central1",
        },
    )()

    with (
        patch(
            "app.services.rag_service.get_rag_service",
        ) as mock_rag_factory,
        patch(
            "app.services.unified_turn_knowledge_context._run_internet_prefetch",
            new=AsyncMock(
                return_value=(
                    "INTERNET RESEARCH (metered; cite URLs when used):\n<internet_research>[]",
                    {"internet_hit_count": 1},
                )
            ),
        ) as mock_internet,
    ):
        mock_rag = mock_rag_factory.return_value
        mock_rag.retrieve_chunks = AsyncMock(return_value=([], {}))

        block, meta = await build_unified_turn_knowledge_context(
            org_id="org-1",
            query="tell me about the best CRM approach for 2026",
            client=object(),
            settings=settings,
            classification={"department": "all"},
        )

    mock_internet.assert_awaited_once()
    assert meta["internal_thin"] is True
    assert "INTERNET RESEARCH" in block
