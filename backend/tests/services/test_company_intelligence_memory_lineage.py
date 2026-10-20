"""Revoked, edited and retired memories cannot reappear through derived snapshots."""
from unittest.mock import AsyncMock

import pytest

from app.services.company_intelligence_collectors import (
    collect_org_memory_digest, memory_digest_provenance, snapshot_memory_digest_is_live,
)
from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator
from tests.services.test_memory_source_liveness import (
    CONNECTORS, LIVE, OFF, ON, ORG, _DB,
)


def _memory():
    return {"id": "m-1", "org_id": ORG, "category": "fact", "content": "Customer detail",
            "source_connector_id": LIVE, "is_active": True}


def _snapshot(memory):
    return {"context_markdown": "### Frequently used agent memories\nCustomer detail",
            "source_counts": {"memory_rows": 1},
            "signals_json": {"memory_digest_provenance": memory_digest_provenance([memory])}}


@pytest.mark.asyncio
async def test_collector_drops_revoked_memories_before_synthesis():
    memory = _memory()
    db = _DB({"agent_memories": [memory], "connectors": [
        {**CONNECTORS[0], "status": "revoked"},
    ]})
    assert await collect_org_memory_digest(ON, ORG, client=db) == []


@pytest.mark.parametrize("change", ["disconnect", "edit", "retire", "delete", "lookup_failure"])
def test_snapshot_drops_copied_memory_when_evidence_no_longer_matches(change):
    memory = _memory()
    snapshot = _snapshot(memory)
    db = _DB({"agent_memories": [memory.copy()], "connectors": [dict(CONNECTORS[0])]})
    assert snapshot_memory_digest_is_live(db, ORG, snapshot, ON) is True
    if change == "disconnect":
        db.tables["connectors"][0]["status"] = "disconnected"
    elif change == "edit":
        db.tables["agent_memories"][0]["content"] = "Changed detail"
    elif change == "retire":
        db.tables["agent_memories"][0]["is_active"] = False
    elif change == "delete":
        db.tables["agent_memories"] = []
    else:
        db.fail_on = "connectors"
    assert snapshot_memory_digest_is_live(db, ORG, snapshot, ON) is False


def test_legacy_snapshot_with_copied_memories_requires_regeneration():
    db = _DB({})
    assert snapshot_memory_digest_is_live(db, ORG, {"source_counts": {"memory_rows": 1}}, ON) is False
    assert snapshot_memory_digest_is_live(db, ORG, {"source_counts": {"memory_rows": 0}}, ON) is True
    assert snapshot_memory_digest_is_live(db, ORG, {}, ON) is False
    assert snapshot_memory_digest_is_live(db, ORG, {}, OFF) is True
    assert db.reads == []


@pytest.mark.asyncio
async def test_shared_chat_voice_prompt_reader_suppresses_snapshot(monkeypatch):
    memory = _memory()
    db = _DB({"agent_memories": [], "connectors": []})
    service = CompanyIntelligenceOrchestrator(settings=ON)
    monkeypatch.setattr(service, "_load_latest_snapshot", AsyncMock(return_value=_snapshot(memory)))
    monkeypatch.setattr(service, "_is_stale", lambda _: False)
    monkeypatch.setattr(service, "_client", lambda: db)
    assert await service.get_context_for_prompt(ORG) == ""
