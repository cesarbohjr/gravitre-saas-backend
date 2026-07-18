from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.unified_retrieval_service import RetrievalScopes, UnifiedRetrievalService


@pytest.mark.asyncio
async def test_unified_retrieval_composes_bundle():
    rag = MagicMock()
    rag.retrieve_hybrid_rows = AsyncMock(
        return_value=(
            [
                {
                    "chunk_id": "c1",
                    "content": "Policy",
                    "score": 0.9,
                    "source_title": "KB",
                }
            ],
            {"reranked": 1},
        )
    )
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)
    client = MagicMock()

    with patch(
        "app.services.unified_retrieval_service.get_org_context_service"
    ) as mock_org_svc:
        mock_org_svc.return_value.get_snapshot.return_value = {
            "connectedIntegrations": ["hubspot"],
            "orgName": "Acme",
        }
        with patch(
            "app.services.unified_retrieval_service.build_task_retrieval_context",
            return_value={"facts": [{"content": "Prefer email"}]},
        ):
            with patch(
                "app.services.unified_retrieval_service.format_retrieval_prompt_section",
                return_value="<agent_memory>mem</agent_memory>",
            ):
                bundle = await service.retrieve(
                    org_id="org-1",
                    query="What is our refund policy?",
                    client=client,
                    agent={"id": "agent-1", "name": "Support"},
                    environment_name="production",
                )

    rag.retrieve_hybrid_rows.assert_awaited_once()
    assert len(bundle.rag_sources) == 1
    assert bundle.org_context["orgName"] == "Acme"
    assert "<knowledge_base>" in bundle.rag_section
    assert bundle.memory_section == "<agent_memory>mem</agent_memory>"
    assert any(source.get("kind") == "knowledge" for source in bundle.sources)


@pytest.mark.asyncio
async def test_unified_retrieval_respects_scopes():
    rag = MagicMock()
    rag.retrieve_chunks = AsyncMock(return_value=([], {}))
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)

    with patch("app.services.unified_retrieval_service.get_org_context_service") as mock_org_svc:
        bundle = await service.retrieve(
            org_id="org-1",
            query="test",
            client=MagicMock(),
            agent={"id": "agent-1"},
            scopes=RetrievalScopes(knowledge=False, org_context=False, agent_memory=False),
        )

    mock_org_svc.return_value.get_snapshot.assert_not_called()
    rag.retrieve_chunks.assert_not_awaited()
    assert bundle.rag_sources == []
    assert bundle.org_context == {}


@pytest.mark.asyncio
async def test_retrieve_knowledge_rows_maps_be10_shape():
    rag = MagicMock()
    rag.retrieve_hybrid_rows = AsyncMock(
        return_value=(
            [
                {
                    "chunk_id": "c1",
                    "content": "Policy text",
                    "source_id": "src-1",
                    "source_title": "HR",
                    "document_id": "doc-1",
                    "document_title": "Handbook",
                    "chunk_index": 2,
                    "score": 0.91,
                }
            ],
            {"reranked": 1},
        )
    )
    service = UnifiedRetrievalService(settings=SimpleNamespace(rag_top_k=5), rag_service=rag)

    rows, metrics = await service.retrieve_knowledge_rows(
        org_id="org-1",
        query="refund policy",
        top_k=5,
        environment_name="production",
        agent_id="agent-1",
        min_score=0.5,
    )

    rag.retrieve_hybrid_rows.assert_awaited_once()
    assert metrics["reranked"] == 1
    assert rows[0]["chunk_id"] == "c1"
    assert rows[0]["content"] == "Policy text"
    assert rows[0]["source_id"] == "src-1"
    assert rows[0]["chunk_index"] == 2


def test_hybrid_row_to_be10_row_defaults_missing_metadata():
    from app.services.unified_retrieval_service import hybrid_row_to_be10_row

    row = hybrid_row_to_be10_row({"id": "abc", "content": "hello", "score": 0.5, "title": "Doc"})
    assert row["chunk_id"] == "abc"
    assert row["source_title"] == "Doc"
    assert row["source_id"] == ""


@pytest.mark.asyncio
async def test_unified_retrieval_internet_stage_when_scope_enabled():
    settings = SimpleNamespace(
        rag_top_k=5,
        internet_research_enabled=True,
        tavily_api_key="tvly-test",
        domain_adaptive_learning_enabled=False,
    )
    rag = MagicMock()
    rag.retrieve_hybrid_rows = AsyncMock(return_value=([], {}))
    service = UnifiedRetrievalService(settings=settings, rag_service=rag)

    with patch("app.services.unified_retrieval_service.get_org_context_service") as mock_org_svc:
        mock_org_svc.return_value.get_snapshot.return_value = {"connectedIntegrations": [], "orgName": "Acme"}
        with patch(
            "app.services.unified_retrieval_service.build_task_retrieval_context",
            return_value={},
        ):
            with patch(
                "app.services.unified_retrieval_service.format_retrieval_prompt_section",
                return_value="",
            ):
                with patch(
                    "app.services.web_research.search_web",
                    AsyncMock(
                        return_value={
                            "totalResults": 1,
                            "results": [
                                {
                                    "title": "Industry update",
                                    "url": "https://example.com/update",
                                    "snippet": "Market moved up 2%.",
                                }
                            ],
                            "sources": [],
                        }
                    ),
                ):
                    bundle = await service.retrieve(
                        org_id="org-1",
                        query="latest market trends",
                        client=MagicMock(),
                        agent={"id": "assistant", "name": "Assistant"},
                        parameters={"research_scope": "internet_research"},
                    )

    assert any(source.get("kind") == "internet" for source in bundle.sources)
    assert bundle.research_cascade["internet_research"]["ran"] is True
    assert bundle.research_cascade["internet_research"]["result_count"] == 1
    assert "<internet_research>" in bundle.rag_section


@pytest.mark.asyncio
async def test_unified_retrieval_pack_stage_when_scope_enabled():
    settings = SimpleNamespace(
        rag_top_k=5,
        internet_research_enabled=False,
        tavily_api_key="",
        domain_adaptive_learning_enabled=False,
    )
    rag = MagicMock()
    rag.retrieve_hybrid_rows = AsyncMock(return_value=([], {}))
    service = UnifiedRetrievalService(settings=settings, rag_service=rag)

    pack_rows = [
        {
            "id": "pack-signal-1",
            "content": "GDP rose 2.1%",
            "score": 0.72,
            "source": "GDP growth signal",
            "title": "GDP growth signal",
            "kind": "intelligence_pack",
            "metadata": {"pack_id": "executive-intelligence-pack", "vendor": "fred", "origin": "external_signals"},
        }
    ]

    with patch("app.services.unified_retrieval_service.get_org_context_service") as mock_org_svc:
        mock_org_svc.return_value.get_snapshot.return_value = {"connectedIntegrations": [], "orgName": "Acme"}
        with patch(
            "app.services.unified_retrieval_service.build_task_retrieval_context",
            return_value={},
        ):
            with patch(
                "app.services.unified_retrieval_service.format_retrieval_prompt_section",
                return_value="",
            ):
                with patch(
                    "app.services.pack_aware_source_selection.retrieve_pack_sources",
                    AsyncMock(
                        return_value={
                            "rows": pack_rows,
                            "pack_ids": ["executive-intelligence-pack"],
                            "catalog_matches": 2,
                            "signal_count": 1,
                            "entity_count": 0,
                            "vendors": ["fred"],
                        }
                    ),
                ):
                    bundle = await service.retrieve(
                        org_id="org-1",
                        query="macro GDP outlook",
                        client=MagicMock(),
                        agent={"id": "assistant", "name": "Assistant"},
                        parameters={
                            "research_scope": "intelligence_packs",
                            "knowledge_assignments": [
                                {
                                    "label": "Executive Intelligence Pack",
                                    "metadata": {"intelligence_pack_id": "executive-intelligence-pack"},
                                }
                            ],
                        },
                    )

    assert any(source.get("kind") == "intelligence_pack" for source in bundle.sources)
    assert bundle.research_cascade["intelligence_packs"]["ran"] is True
    assert bundle.research_cascade["intelligence_packs"]["result_count"] == 1
    assert "<intelligence_pack_sources>" in bundle.rag_section
