"""ECO-003: cross-tenant and fallback behavior through real ContextAssembler."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import context_assembler as module


def bundle_for(org: str):
    return SimpleNamespace(
        rag_sources=[{"content": f"row:{org}", "document_id": f"doc:{org}", "score": 1.0}],
        memory_context={"owner": org},
        graph_context={"owner": org},
        sources=[{"owner": org}],
        org_context={"owner": org},
        retrieval_plan={"scope": org},
        retrieval_effectiveness={"owner": org},
    )


@pytest.mark.asyncio
async def test_two_tenants_do_not_share_context_or_retrieval_parameters(monkeypatch):
    captured = []

    async def retrieve(**kwargs):
        captured.append(kwargs)
        return bundle_for(kwargs["org_id"])

    retrieval = SimpleNamespace(retrieve=AsyncMock(side_effect=retrieve))
    company = SimpleNamespace(get_context_for_prompt=AsyncMock(side_effect=lambda org_id: {"owner": org_id}))
    monkeypatch.setattr(module, "get_unified_retrieval_service", lambda: retrieval)
    monkeypatch.setattr(module, "get_company_intelligence_orchestrator", lambda: company)

    assembler = module.ContextAssembler(settings=SimpleNamespace())
    db_client = object()
    a = await assembler.assemble(
        "tenant-A", "user-A", "request A", {"intent": "question", "requires_web_search": False},
        client=db_client, agent={"id": "agent-A"}, environment_name="qa-A",
    )
    b = await assembler.assemble(
        "tenant-B", "user-B", "request B", {"intent": "question", "requires_web_search": False},
        client=db_client, agent={"id": "agent-B"}, environment_name="qa-B",
    )

    assert [call["org_id"] for call in captured] == ["tenant-A", "tenant-B"]
    assert [call["user_id"] for call in captured] == ["user-A", "user-B"]
    assert [call["environment_name"] for call in captured] == ["qa-A", "qa-B"]
    assert [call["agent"]["id"] for call in captured] == ["agent-A", "agent-B"]
    assert all(call["client"] is db_client for call in captured)
    assert all(call["scopes"].org_context and call["scopes"].agent_memory and call["scopes"].knowledge for call in captured)
    assert a["memory_context"]["owner"] == "tenant-A"
    assert b["memory_context"]["owner"] == "tenant-B"
    assert a["company_intelligence"]["owner"] == "tenant-A"
    assert b["company_intelligence"]["owner"] == "tenant-B"
    assert a["rag_context"][0]["documentId"] != b["rag_context"][0]["documentId"]
    assert not a["external_context"] and not b["external_context"]


@pytest.mark.asyncio
async def test_retrieval_error_keeps_existing_empty_fallback(monkeypatch):
    retrieval = SimpleNamespace(retrieve=AsyncMock(side_effect=RuntimeError("downstream unavailable")))
    company = SimpleNamespace(get_context_for_prompt=AsyncMock(return_value={"status": "available"}))
    monkeypatch.setattr(module, "get_unified_retrieval_service", lambda: retrieval)
    monkeypatch.setattr(module, "get_company_intelligence_orchestrator", lambda: company)

    result = await module.ContextAssembler(settings=SimpleNamespace()).assemble(
        "tenant-A", "user-A", "non-sensitive test request",
        {"requires_web_search": False}, client=object(), environment_name="qa",
    )
    assert result["rag_context"] == []
    assert result["memory_context"] == {}
    assert result["org_context"] == {}
    assert result["retrieval_plan"] == {}
    assert result["company_intelligence"] == {"status": "available"}


@pytest.mark.asyncio
async def test_research_only_for_classification_request_and_same_tenant(monkeypatch):
    retrieval = SimpleNamespace(retrieve=AsyncMock(return_value=bundle_for("tenant-A")))
    company = SimpleNamespace(get_context_for_prompt=AsyncMock(return_value={}))
    research = SimpleNamespace(research=AsyncMock(return_value={"findings": ["non-sensitive"]}))
    monkeypatch.setattr(module, "get_unified_retrieval_service", lambda: retrieval)
    monkeypatch.setattr(module, "get_company_intelligence_orchestrator", lambda: company)
    monkeypatch.setattr(module, "get_research_service", lambda settings: research)

    assembler = module.ContextAssembler(settings=SimpleNamespace())
    result = await assembler.assemble(
        "tenant-A", "user-A", "search allowed", {"requires_web_search": True},
        client=object(), environment_name="qa",
    )
    assert result["external_context"] == {"findings": ["non-sensitive"]}
    research.research.assert_awaited_once_with("tenant-A", "search allowed", depth="standard")
