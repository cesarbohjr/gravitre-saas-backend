"""Phase 1: relationship rebuild never leaves the graph empty on failure (upsert first, prune after)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import entity_relationship_builder as erb

OLD = "2026-01-01T00:00:00+00:00"


class _Table:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self._filters: list = []
        self._op = "select"
        self._payload: dict | None = None

    def select(self, *_a):
        self._op = "select"
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters.append(lambda r: r.get(col) == val)
        return self

    def lt(self, col, val):
        cut = datetime.fromisoformat(val)
        self._filters.append(lambda r: datetime.fromisoformat(r[col]) < cut)
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        match = [r for r in self.rows if all(f(r) for f in self._filters)]
        if self._op == "insert":
            row = dict(self._payload, id=f"e{len(self.rows) + 1}")
            self.rows.append(row)
            return SimpleNamespace(data=[row])
        if self._op == "update":
            for r in match:
                r.update(self._payload)
        if self._op == "delete":
            for r in match:
                self.rows.remove(r)
        return SimpleNamespace(data=[dict(r) for r in match])


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "org_entity_relationships"
        return _Table(self.rows)


def _edge(eid, target, evidence=5):
    return {
        "id": eid,
        "org_id": "org-1",
        "source_entity_type": "glossary_term",
        "source_entity_id": "t1",
        "relationship_type": "associated-department",
        "target_entity_type": "department",
        "target_entity_id": target,
        "evidence_count": evidence,
        "confidence": 0.5,
        "last_observed_at": OLD,
    }


async def _glossary_builder(org_id, *, settings=None, client=None):
    erb._upsert_relationship(
        client,
        org_id=org_id,
        source_entity_type="glossary_term",
        source_entity_id="t1",
        relationship_type="associated-department",
        target_entity_type="department",
        target_entity_id="d-keep",
        confidence=0.7,
        evidence_count=2,
    )
    return 1


async def _zero(*_a, **_k):
    return 0


async def _boom(*_a, **_k):
    raise RuntimeError("agent_action_outcomes unavailable")


@pytest.mark.asyncio
async def test_failed_rebuild_keeps_existing_edges():
    rows = [_edge("e1", "d-keep"), _edge("e2", "d-stale")]
    db = _Db(rows)
    with patch.object(erb, "build_relationships_from_glossary", _glossary_builder), patch.object(
        erb, "build_relationships_from_agent_memories", _zero
    ), patch.object(erb, "build_relationships_from_query_clusters", _zero), patch.object(
        erb, "build_relationships_from_crm_data", _boom
    ):
        with pytest.raises(RuntimeError):
            await erb.rebuild_org_entity_relationships("org-1", settings=SimpleNamespace(), client=db)
    assert {r["target_entity_id"] for r in rows} == {"d-keep", "d-stale"}
    assert erb._REBUILD_STARTED_AT.get() is None


@pytest.mark.asyncio
async def test_successful_rebuild_prunes_only_unobserved_edges_and_restates_evidence():
    rows = [_edge("e1", "d-keep"), _edge("e2", "d-stale")]
    db = _Db(rows)
    with patch.object(erb, "build_relationships_from_glossary", _glossary_builder), patch.object(
        erb, "build_relationships_from_agent_memories", _zero
    ), patch.object(erb, "build_relationships_from_query_clusters", _zero), patch.object(
        erb, "build_relationships_from_crm_data", _zero
    ):
        summary = await erb.rebuild_org_entity_relationships("org-1", settings=SimpleNamespace(), client=db)
    assert summary["total"] == 1
    assert [r["target_entity_id"] for r in rows] == ["d-keep"]
    kept = rows[0]
    assert kept["id"] == "e1"  # updated in place, not deleted and re-inserted
    assert kept["evidence_count"] == 2  # restated, not 5 + 2
    assert datetime.fromisoformat(kept["last_observed_at"]) > datetime.fromisoformat(OLD)


def test_upsert_outside_rebuild_still_accumulates():
    rows = [_edge("e1", "d-keep")]
    erb._upsert_relationship(
        _Db(rows),
        org_id="org-1",
        source_entity_type="glossary_term",
        source_entity_id="t1",
        relationship_type="associated-department",
        target_entity_type="department",
        target_entity_id="d-keep",
        confidence=0.7,
        evidence_count=2,
    )
    assert rows[0]["evidence_count"] == 7
