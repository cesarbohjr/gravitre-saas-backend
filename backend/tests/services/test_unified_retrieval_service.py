from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.unified_retrieval_service import RetrievalScopes, UnifiedRetrievalService


@pytest.mark.asyncio
async def test_unified_retrieval_composes_bundle():
    rag = MagicMock()
    rag.retrieve_chunks = AsyncMock(
        return_value=(
            [SimpleNamespace(id="c1", content="Policy", score=0.9, source="KB")],
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

    rag.retrieve_chunks.assert_awaited_once()
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
