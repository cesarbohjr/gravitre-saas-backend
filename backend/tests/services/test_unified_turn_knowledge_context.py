"""Tests for unified-turn knowledge prefetch."""
from __future__ import annotations

from types import SimpleNamespace
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
        ("What can you help me with?", False),
        ("what tools do you have access to?", False),
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
            # This test covers the original thinness escalation on its own.
            # The sufficiency loop has its own suite in
            # test_evidence_sufficiency_loop.py; keeping it off here means a
            # failure points at one mechanism, not two.
            "evidence_sufficiency_loop_enabled": False,
            "evidence_contradiction_check_enabled": False,
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
                    [{"kind": "internet", "content": "web result"}],
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


@pytest.mark.asyncio
async def test_active_context_ranking_deduplicates_and_includes_connected_tool_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import adaptive_research_cascade as cascade
    from app.services import unified_turn_knowledge_context as context_module
    import app.knowledge_fabric.tool_knowledge as tool_knowledge

    observed: dict[str, list[str]] = {}

    async def packs(**kwargs):
        observed["pack_ids"] = list(kwargs["pack_ids"])
        return (
            "PACK LEGACY",
            {"fabric_hit_count": 1},
            [
                {
                    "kind": "knowledge_pack",
                    "content": "shared evidence",
                    "source": "same-source",
                    "authority_score": 0.9,
                }
            ],
        )

    async def rag(**kwargs):
        return (
            "RAG LEGACY",
            {"org_rag_chunk_count": 1},
            [
                {
                    "kind": "knowledge",
                    "content": "shared evidence",
                    "source": "same-source",
                    "score": 0.7,
                }
            ],
        )

    monkeypatch.setattr(context_module, "_retrieve_knowledge_packs", packs)
    monkeypatch.setattr(context_module, "_retrieve_org_rag", rag)
    monkeypatch.setattr(cascade, "assess_internal_retrieval_thinness", lambda **_: False)
    monkeypatch.setattr(cascade, "should_run_internet_research", lambda *a, **k: False)
    monkeypatch.setattr(
        tool_knowledge,
        "tool_packs_for_connected_vendors",
        lambda connected: ["pack.tool.hubspot"] if "hubspot" in connected else [],
    )

    block, meta = await build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What does our connected CRM policy require?",
        client=object(),
        settings=SimpleNamespace(
            evidence_sufficiency_loop_enabled=False,
            evidence_sufficiency_max_rounds=0,
            evidence_contradiction_check_enabled=False,
            cross_source_context_engine_shadow_enabled=True,
            cross_source_context_engine_enabled=True,
            cross_source_context_token_budget=1000,
        ),
        classification={"department": "legal", "intent": "knowledge_lookup"},
        knowledge_assignments=[
            {"source_type": "knowledge_pack", "source_id": "pack.legal", "enabled": True}
        ],
        connected_integrations=["hubspot"],
        supplemental_context={
            "memory_section": "<memory>remember this account</memory>",
            "knowledge_section": (
                "<knowledge_fabric>shared evidence</knowledge_fabric>\n"
                "<org_metric_definitions>ARR is org-defined</org_metric_definitions>"
            ),
            "outcome_bias_section": "<outcome_bias>prefer the proven path</outcome_bias>",
        },
    )

    ranking = meta["contextRanking"]
    assert ranking["mode"] == "active"
    assert ranking["candidateCount"] == 4
    assert ranking["selectedCount"] == 3
    assert ranking["duplicateCount"] == 1
    assert ranking["managedSupplementalSections"] is True
    assert ranking["kernelFabricExcludedFromRanking"] is True
    assert "pack.tool.hubspot" in observed["pack_ids"]
    assert block.count("shared evidence") == 1
    assert "remember this account" in block
    assert "ARR is org-defined" in block
    assert block.count("prefer the proven path") == 1
    assert "PACK LEGACY" not in block


@pytest.mark.asyncio
async def test_shadow_context_ranking_preserves_legacy_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import adaptive_research_cascade as cascade
    from app.services import unified_turn_knowledge_context as context_module

    async def rag(**kwargs):
        return (
            "RAG LEGACY",
            {"org_rag_chunk_count": 1},
            [{"kind": "knowledge", "content": "rank me", "source": "doc-1", "score": 0.8}],
        )

    monkeypatch.setattr(context_module, "_retrieve_org_rag", rag)
    monkeypatch.setattr(cascade, "assess_internal_retrieval_thinness", lambda **_: False)
    monkeypatch.setattr(cascade, "should_run_internet_research", lambda *a, **k: False)

    block, meta = await build_unified_turn_knowledge_context(
        org_id="org-1",
        query="What does the document say?",
        client=object(),
        settings=SimpleNamespace(
            evidence_sufficiency_loop_enabled=False,
            evidence_sufficiency_max_rounds=0,
            evidence_contradiction_check_enabled=False,
            cross_source_context_engine_shadow_enabled=True,
            cross_source_context_engine_enabled=False,
            cross_source_context_token_budget=1000,
        ),
        classification={"department": "all", "intent": "knowledge_lookup"},
    )

    assert meta["contextRanking"]["mode"] == "shadow"
    assert "RAG LEGACY" in block
