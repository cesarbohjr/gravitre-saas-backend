"""Post Phase F follow-on integration tests."""
from __future__ import annotations

import pytest

from app.services.platform_intelligence_dedup import (
    build_intelligence_dedup_key,
    dedupe_intelligence_records,
    should_skip_duplicate_event,
)
from app.services.rl_policy_gate import get_rl_policy_status, neural_rl_signoff_granted


def test_rl_policy_gate_defaults_to_tabular_v3():
    status = get_rl_policy_status()
    assert status["active_bandit_version"] == "v3"
    assert status["tabular_ledger_v2"] == "live"
    assert status["tabular_ledger_v3"] == "live"
    assert status["bandit_v2_fallback"] is True
    assert status["memory_conflicts"] == "live"
    assert status["phase_e_status"] == "complete"
    assert status["neural_rl_enabled"] is False
    assert status["neural_rl_status"] == "planned"
    assert status["world_models_status"] == "planned"
    assert status["federated_learning"] == "disabled"


def test_neural_rl_requires_explicit_signoff(monkeypatch):
    monkeypatch.delenv("GRAVITRE_NEURAL_RL_SIGNOFF", raising=False)
    assert neural_rl_signoff_granted() is False
    monkeypatch.setenv("GRAVITRE_NEURAL_RL_SIGNOFF", "approved")
    assert neural_rl_signoff_granted() is True


def test_platform_dedup_skips_repeated_events():
    key = build_intelligence_dedup_key("org-1", "assistant", "message", "m-1", "response")
    assert should_skip_duplicate_event(key, ttl_seconds=60) is False
    assert should_skip_duplicate_event(key, ttl_seconds=60) is True


def test_dedupe_intelligence_records():
    rows = [
        {"org_id": "org-1", "surface": "a", "entity_type": "m", "entity_id": "1", "event_type": "x"},
        {"org_id": "org-1", "surface": "a", "entity_type": "m", "entity_id": "1", "event_type": "x"},
        {"org_id": "org-1", "surface": "b", "entity_type": "m", "entity_id": "2", "event_type": "x"},
    ]
    assert len(dedupe_intelligence_records(rows)) == 2


@pytest.mark.asyncio
async def test_external_wikipedia_fetch(monkeypatch):
    from app.services import external_knowledge_service as svc

    async def fake_summary(topic: str, **kwargs):
        return {"type": "external_wikipedia", "summary": "Test", "source": "https://example.test"}

    monkeypatch.setattr(svc, "fetch_wikipedia_summary", fake_summary)
    rows = await svc.gather_external_knowledge("Gravitre")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_external_pubmed_fetch(monkeypatch):
    from app.services import external_knowledge_service as svc

    async def fake_pubmed(topic: str, **kwargs):
        return [
            {
                "type": "external_pubmed",
                "title": "Sample trial",
                "summary": "Sample trial",
                "source": "https://pubmed.ncbi.nlm.nih.gov/123/",
                "provider": "pubmed",
            }
        ]

    monkeypatch.setattr(svc, "fetch_pubmed_summaries", fake_pubmed)
    rows = await svc.gather_external_knowledge("diabetes treatment", include_wikipedia=False)
    assert len(rows) == 1
    assert rows[0]["type"] == "external_pubmed"


def test_infer_external_knowledge_domain():
    from app.services.external_knowledge_service import infer_external_knowledge_domain

    assert infer_external_knowledge_domain("What is Gravitre?") == "general"
    assert infer_external_knowledge_domain("PubMed trials for oncology") == "healthcare"
    assert infer_external_knowledge_domain("topic", explicit_domain="pharma") == "pharma"


@pytest.mark.asyncio
async def test_process_conformance_empty_inventory():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.process_mining_service import ProcessMiningService

    service = ProcessMiningService()
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(service, "_client", return_value=mock_client):
        with patch.object(service, "discover_workflow_patterns", AsyncMock(return_value={"patterns": []})):
            result = await service.check_process_conformance("org-1")
    assert result["status"] == "ok"
    assert result["declared_process_count"] == 0
