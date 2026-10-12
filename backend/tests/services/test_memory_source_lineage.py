"""Memory lineage writers: connector id / record ref reach agent_memories rows.

The purge SQL runs against real PostgreSQL in tests/db/test_memory_source_lineage_pg.py.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.services.memory_contamination_guard import (
    SOURCE_UNTRUSTED_EXTERNAL,
    memory_source_lineage,
    without_lineage,
)
from app.services.memory_extraction_service import extract_typed_memories_structured
from app.services.memory_temporal_service import upsert_temporal_memory
from app.services.workspace_memory_service import promote_turn_memories

ORG = "11111111-1111-4111-8111-111111111111"
CONN = "AAAAAAAA-0000-4000-8000-000000000001"
CONN_LOWER = CONN.lower()
ON = SimpleNamespace(memory_source_lineage_enabled=True)
OFF = SimpleNamespace(memory_source_lineage_enabled=False)


class _Query:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.payload: dict[str, Any] | None = None
        self.op = "select"

    def insert(self, payload):
        self.op = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload):
        self.op = "update"
        self.payload = dict(payload)
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        if self.op == "insert":
            assert self.payload is not None
            self.client.attempts.append(self.payload)
            if self.client.missing_lineage_columns and "source_connector_id" in self.payload:
                raise RuntimeError("column agent_memories.source_connector_id does not exist")
            self.client.inserted.append(self.payload)
            return SimpleNamespace(data=[{**self.payload, "id": self.payload.get("id") or "m-1"}])
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self, *, missing_lineage_columns: bool = False) -> None:
        self.missing_lineage_columns = missing_lineage_columns
        self.attempts: list[dict[str, Any]] = []
        self.inserted: list[dict[str, Any]] = []

    def table(self, _name):
        return _Query(self)


@pytest.fixture(autouse=True)
def _no_embedding(monkeypatch):
    monkeypatch.setattr("app.rag.embedding.get_embedding", lambda *a, **k: None)


# ------------------------------------------------------------------ helper


def test_lineage_off_by_default():
    assert memory_source_lineage({"source_connector_id": CONN}, settings=SimpleNamespace()) == {}
    assert memory_source_lineage({"source_connector_id": CONN}, settings=OFF) == {}


def test_lineage_takes_connector_row_ids_only():
    assert memory_source_lineage({"connector_id": CONN, "record_ref": "deal:42"}, settings=ON) == {
        "source_connector_id": CONN_LOWER,
        "source_record_ref": "deal:42",
    }
    # An integration slug names a vendor, not a connection.
    assert memory_source_lineage({"connector_id": "hubspot", "record_ref": "deal:42"}, settings=ON) == {}
    long_ref = memory_source_lineage({"source_connector_id": CONN, "source_record_ref": "x" * 900}, settings=ON)
    assert len(long_ref["source_record_ref"]) == 500
    assert without_lineage({"a": 1, **long_ref}) == {"a": 1}


# ------------------------------------------------------------------ extraction


def test_external_candidate_keeps_lineage_keys():
    rows = extract_typed_memories_structured(
        {
            "external_memory_candidate": {
                "content": "Acme renews in March",
                "provenance": "connector:hubspot",
                "connector_id": CONN,
                "source_record_ref": "deal:42",
            }
        }
    )
    assert len(rows) == 1
    assert rows[0]["source_class"] == SOURCE_UNTRUSTED_EXTERNAL
    assert memory_source_lineage(rows[0], settings=ON) == {
        "source_connector_id": CONN_LOWER,
        "source_record_ref": "deal:42",
    }


def test_outcome_of_acting_on_a_connection_carries_it():
    rows = extract_typed_memories_structured(
        {"action": "hubspot.create_contact", "status": "failed", "connector_id": CONN},
        outcome_event="workflow_failed",
    )
    outcome = next(r for r in rows if r.get("category") == "outcome")
    assert memory_source_lineage(outcome, settings=ON)["source_connector_id"] == CONN_LOWER


def test_typed_and_decision_memories_without_lineage_stay_untagged():
    rows = extract_typed_memories_structured(
        {"memory_content": "Use net-30", "memory_category": "decision", "typed_memories": [{"content": "x"}]},
        provenance="user_statement",
    )
    assert rows and all(memory_source_lineage(r, settings=ON) == {} for r in rows)


# ------------------------------------------------------------------ workspace writer


def _promote(client: _Client, settings: Any, memory: dict[str, Any]) -> list[dict[str, Any]]:
    return promote_turn_memories(client, org_id=ORG, memories=[memory], settings=settings)


def test_promote_writes_lineage_columns_when_enabled():
    client = _Client()
    _promote(client, ON, {"content": "Acme renews in March", "category": "episodic", "connector_id": CONN,
                          "record_ref": "deal:42", "from_untrusted_external": True})
    assert client.inserted[0]["source_connector_id"] == CONN_LOWER
    assert client.inserted[0]["source_record_ref"] == "deal:42"
    assert client.inserted[0]["source_class"] == SOURCE_UNTRUSTED_EXTERNAL


def test_promote_writes_nothing_new_when_disabled():
    client = _Client()
    _promote(client, OFF, {"content": "Acme renews in March", "category": "episodic", "connector_id": CONN})
    assert "source_connector_id" not in client.inserted[0]
    assert "source_record_ref" not in client.inserted[0]


def test_promote_retries_without_lineage_when_columns_are_missing():
    client = _Client(missing_lineage_columns=True)
    written = _promote(client, ON, {"content": "Acme renews in March", "category": "episodic", "connector_id": CONN})
    assert len(written) == 1
    assert len(client.attempts) == 2
    # The hardened columns survive; only the lineage columns are dropped.
    assert "source_connector_id" not in client.inserted[0]
    assert client.inserted[0]["is_current"] is True and "source_class" in client.inserted[0]


def test_temporal_memory_carries_lineage_and_retries_without_it():
    memory = {"content": "ICP: 10-50 employees", "category": "preference", "connector_id": CONN}
    client = _Client()
    _promote(client, ON, memory)
    assert client.inserted[0]["memory_key"] and client.inserted[0]["source_connector_id"] == CONN_LOWER

    missing = _Client(missing_lineage_columns=True)
    row = upsert_temporal_memory(
        missing,
        {"org_id": ORG, "content": "ICP: 10-50", "category": "preference", "source_connector_id": CONN_LOWER},
    )
    assert row is not None
    assert len(missing.attempts) == 2 and "source_connector_id" not in missing.inserted[0]


# ------------------------------------------------------------------ create_agent_memory


@patch("app.services.agent_memory_service.get_embedding", return_value=None)
def test_create_agent_memory_tags_and_falls_back(_embed):
    from app.services.agent_memory_service import create_agent_memory

    client = _Client()
    create_agent_memory(
        ON, client, ORG, None, user_id=None, content="Acme renews in March", category="fact",
        provenance="connector:hubspot", source_connector_id=CONN, source_record_ref="deal:42",
    )
    assert client.inserted[0]["source_connector_id"] == CONN_LOWER
    assert client.inserted[0]["source_record_ref"] == "deal:42"

    off = _Client()
    create_agent_memory(OFF, off, ORG, None, user_id=None, content="x fact", source_connector_id=CONN)
    assert "source_connector_id" not in off.inserted[0]

    missing = _Client(missing_lineage_columns=True)
    create_agent_memory(
        ON, missing, ORG, None, user_id=None, content="Acme renews in March", source_connector_id=CONN,
    )
    assert len(missing.attempts) == 2
    assert "source_connector_id" not in missing.inserted[0]
    assert missing.inserted[0]["source_class"]  # kept: only lineage was missing
