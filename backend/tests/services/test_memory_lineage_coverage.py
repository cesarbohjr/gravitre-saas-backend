"""Lineage coverage for every memory writer, and the connector-derived ones in detail.

The writer inventory below lists every place that writes ``agent_memories``,
``entity_observations`` or ``entity_behavior_signals`` (directly or through a writer
helper), with whether it is connector-derived and how its lineage is carried. A new
writer fails ``test_every_memory_writer_is_classified`` until it is added here (and
to docs/delivery/memory-lineage-writer-inventory-2026-10-12.md).

The purge and superseded-value rules run against real PostgreSQL in
tests/db/test_memory_source_lineage_pg.py and tests/db/test_source_scoped_observation_purge_pg.py.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import entity_observations as eo
from app.services.memory_contamination_guard import (
    SOURCE_UNTRUSTED_EXTERNAL,
    lineage_required,
)
from app.services.memory_extraction_service import extract_typed_memories_structured
from app.services.workspace_memory_service import promote_turn_memories
from tests.services.test_entity_observations import (  # noqa: F401
    _feed_event,
    _FeedClient,
    _hubspot,
)

APP = Path(__file__).resolve().parents[2] / "app"
ORG = "11111111-1111-4111-8111-111111111111"
CONN = "aaaaaaaa-0000-4000-8000-000000000001"
OTHER_CONN = "aaaaaaaa-0000-4000-8000-000000000002"
ON = SimpleNamespace(memory_source_lineage_enabled=True)
OFF = SimpleNamespace(memory_source_lineage_enabled=False)

# (file relative to app/, writer) -> (call sites, classification)
CONNECTOR_TAGGED = "connector-derived: tagged with source_connector_id; refused untagged when lineage is on"
CONNECTOR_INHERITED = "carries the act's connector lineage when the act names one"
NOT_CONNECTOR = "not connector-derived"
WRITER_INVENTORY: dict[tuple[str, str], tuple[int, str]] = {
    # agent_memories
    ("services/chat_connector_execution_service.py", "promote_turn_memories"): (1, CONNECTOR_TAGGED),
    ("services/cognitive_turn_kernel.py", "promote_turn_memories"): (1, CONNECTOR_INHERITED),
    ("routers/ops_internal.py", "promote_turn_memories"): (2, NOT_CONNECTOR + ": synthetic probe rows"),
    ("routers/ops_internal.py", "table:agent_memories"): (1, NOT_CONNECTOR + ": cross-org isolation probe"),
    ("routers/agent_memories.py", "create_agent_memory"): (1, NOT_CONNECTOR + ": user-direct memory API"),
    ("services/agent_memory_service.py", "create_agent_memory"): (
        4,
        NOT_CONNECTOR + ": remember_* outcome helpers over Gravitre feedback/approval/prediction events",
    ),
    ("services/agent_memory_service.py", "remember_user_preference"): (1, NOT_CONNECTOR),
    ("services/agent_memory_service.py", "remember_workflow_outcome"): (1, NOT_CONNECTOR),
    ("services/agent_memory_service.py", "remember_approval_pattern"): (1, NOT_CONNECTOR),
    ("services/agent_memory_service.py", "remember_prediction_outcome"): (1, NOT_CONNECTOR),
    ("services/agent_memory_service.py", "table:agent_memories"): (
        3,
        "create_agent_memory insert and its retries; tags when given source_connector_id",
    ),
    ("workflows/execution_engine_runtime.py", "create_agent_memory"): (
        1,
        NOT_CONNECTOR + ": workflow run id, status and Gravitre step errors",
    ),
    ("services/memory_promotion_service.py", "_write_memories"): (
        1,
        NOT_CONNECTOR + ": aggregates of glossary, workflow runs, query patterns, approvals",
    ),
    ("services/memory_promotion_service.py", "table:agent_memories"): (1, NOT_CONNECTOR),
    ("services/workspace_memory_service.py", "upsert_temporal_memory"): (1, "promote_turn_memories internals"),
    ("services/workspace_memory_service.py", "_insert_memory_row"): (1, "promote_turn_memories internals"),
    ("services/workspace_memory_service.py", "table:agent_memories"): (3, "promote_turn_memories internals"),
    ("services/memory_temporal_service.py", "_insert_memory"): (2, "upsert_temporal_memory internals"),
    ("services/memory_temporal_service.py", "table:agent_memories"): (2, "upsert_temporal_memory internals"),
    # entity_observations (TABLE) / entity_behavior_signals
    ("services/entity_observations.py", "record_observations"): (1, CONNECTOR_TAGGED),
    ("services/entity_observations.py", "table:TABLE"): (2, "record_observations insert and its retry"),
}

_TABLE_WRITE = re.compile(
    r'table\(\s*(?:"(agent_memories|entity_observations|entity_behavior_signals)"|(TABLE))\s*\)\s*\.(?:insert|upsert)\('
)
_WRITER_CALL = re.compile(
    r"(?<![\w.])(?:\w+\.)?(create_agent_memory|promote_turn_memories|upsert_temporal_memory|record_observations"
    r"|remember_user_preference|remember_workflow_outcome|remember_approval_pattern|remember_prediction_outcome"
    r"|_write_memories|_insert_memory_row|_insert_memory)\("
)
# Modules whose own TABLE constant names one of the memory tables.
_MEMORY_TABLE_MODULES = {"services/entity_observations.py"}


def _scan() -> Counter:
    found: Counter = Counter()
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        text = path.read_text()
        for m in _TABLE_WRITE.finditer(text):
            if m.group(2) and rel not in _MEMORY_TABLE_MODULES:
                continue
            found[(rel, f"table:{m.group(1) or 'TABLE'}")] += 1
        for m in _WRITER_CALL.finditer(text):
            line = text[: m.start()].rsplit("\n", 1)[-1]
            if re.match(r"\s*(async\s+)?def\s", line):
                continue
            found[(rel, m.group(1))] += 1
    return found


def test_every_memory_writer_is_classified():
    found = _scan()
    expected = Counter({k: n for k, (n, _why) in WRITER_INVENTORY.items()})
    assert found == expected, (
        "memory writers changed; classify each new one (connector-derived writers must carry "
        f"source_connector_id): added={dict(found - expected)} removed={dict(expected - found)}"
    )


def test_observations_table_constant_is_the_memory_table():
    assert eo.TABLE == "entity_observations"


# ------------------------------------------------------------------ extraction inherits act lineage


def test_typed_memories_inherit_the_acts_connector():
    act = {
        "source_connector_id": CONN,
        "source_record_ref": "deal:42",
        "typed_memories": [{"content": "Acme renews in March", "category": "episodic"}],
        "external_memory_candidate": {"content": "Customer said: renew in March"},
    }
    out = extract_typed_memories_structured(act, provenance="connector_confirm")
    assert len(out) == 2
    assert all(m["source_connector_id"] == CONN and m["source_record_ref"] == "deal:42" for m in out)
    assert out[1]["source_class"] == SOURCE_UNTRUSTED_EXTERNAL


def test_candidate_naming_its_own_connector_never_gets_another_connectors_record_ref():
    act = {
        "source_connector_id": CONN,
        "source_record_ref": "deal:42",
        "typed_memories": [{"content": "Runbook step", "category": "procedural", "source_connector_id": OTHER_CONN}],
    }
    [m] = extract_typed_memories_structured(act)
    assert m["source_connector_id"] == OTHER_CONN
    assert "source_record_ref" not in m


def test_status_only_outcome_carries_no_lineage():
    # The kernel LEARN stage passes status summaries, not connector content.
    out = extract_typed_memories_structured(
        {"status": "completed", "success": True, "action": "execute_task"}, outcome_event="workflow_executed"
    )
    assert len(out) == 1 and "source_connector_id" not in out[0]


# ------------------------------------------------------------------ workspace writer refuses untagged external content


class _Rows:
    def __init__(self) -> None:
        self.inserted: list[dict[str, Any]] = []

    def table(self, _name):
        rows = self

        class _Q:
            def __init__(self) -> None:
                self.payload: dict[str, Any] | None = None

            def insert(self, payload):
                self.payload = dict(payload)
                return self

            def update(self, payload):
                return self

            def select(self, *_a, **_k):
                return self

            def eq(self, *_a):
                return self

            def limit(self, *_a):
                return self

            def execute(self):
                if self.payload is not None:
                    rows.inserted.append(self.payload)
                    return SimpleNamespace(data=[{**self.payload, "id": "m-1"}])
                return SimpleNamespace(data=[])

        return _Q()


@pytest.fixture(autouse=True)
def _no_embedding(monkeypatch):
    monkeypatch.setattr("app.rag.embedding.get_embedding", lambda *a, **k: None)


def _external(**kw) -> dict[str, Any]:
    return {"content": "Their CFO prefers quarterly billing", "category": "episodic", "from_untrusted_external": True, **kw}


def test_untagged_external_content_is_not_stored_when_lineage_is_on():
    client = _Rows()
    assert promote_turn_memories(client, org_id=ORG, memories=[_external()], settings=ON) == []
    assert client.inserted == []


def test_tagged_external_content_is_stored_with_its_connector():
    client = _Rows()
    promote_turn_memories(client, org_id=ORG, memories=[_external(source_connector_id=CONN)], settings=ON)
    assert client.inserted[0]["source_connector_id"] == CONN
    assert client.inserted[0]["source_class"] == SOURCE_UNTRUSTED_EXTERNAL


def test_flag_off_keeps_todays_behaviour():
    client = _Rows()
    promote_turn_memories(client, org_id=ORG, memories=[_external(source_connector_id=CONN)], settings=OFF)
    assert len(client.inserted) == 1 and "source_connector_id" not in client.inserted[0]


def test_user_statements_need_no_connector():
    client = _Rows()
    promote_turn_memories(
        client,
        org_id=ORG,
        memories=[{"content": "Our ICP is 50-200 employees", "category": "preference"}],
        provenance="user_statement",
        settings=ON,
    )
    assert len(client.inserted) == 1 and "source_connector_id" not in client.inserted[0]


def test_lineage_required_follows_the_flag():
    assert lineage_required(ON) is True
    assert lineage_required(OFF) is False
    assert lineage_required(SimpleNamespace()) is False


# ------------------------------------------------------------------ observations


class _ObsStore:
    def __init__(self, *, missing_column: bool = False) -> None:
        self.missing_column = missing_column
        self.rows: list[dict[str, Any]] = []
        self.attempts = 0

    def table(self, name):
        store = self
        assert name == eo.TABLE

        class _Q:
            def upsert(self, rows, **kw):
                self.rows = rows
                return self

            def execute(self):
                store.attempts += 1
                if store.missing_column and any("source_connector_id" in r for r in self.rows):
                    raise RuntimeError("column entity_observations.source_connector_id does not exist")
                store.rows.extend(self.rows)
                return SimpleNamespace(data=[])

        return _Q()


def _message(connector_id: str = CONN) -> eo.CustomerMessage:
    return eo.CustomerMessage(
        text="We are evaluating other vendors.",
        source_system="hubspot",
        source_record_type="email",
        source_record_id="em1",
        observed_at="2026-10-10T10:00:00Z",
        author_email="buyer@customer.com",
        connector_id=connector_id,
    )


_OBS = [eo.Observation("sentiment", "negative", -1.0, 0.9, "evaluating other vendors")]


def test_observations_name_their_connector():
    store = _ObsStore()
    assert eo.record_observations(store, org_id=ORG, entity_row_id="e1", message=_message(), observations=_OBS, settings=ON) == 1
    assert store.rows[0]["source_connector_id"] == CONN
    assert store.rows[0]["source_system"] == "hubspot"


def test_observation_without_a_connector_is_not_stored_when_lineage_is_on():
    store = _ObsStore()
    n = eo.record_observations(store, org_id=ORG, entity_row_id="e1", message=_message(""), observations=_OBS, settings=ON)
    assert n == 0 and store.rows == [] and store.attempts == 0


def test_observations_flag_off_unchanged():
    store = _ObsStore()
    eo.record_observations(store, org_id=ORG, entity_row_id="e1", message=_message(), observations=_OBS, settings=OFF)
    assert "source_connector_id" not in store.rows[0]


def test_observations_written_without_the_column_before_the_migration():
    store = _ObsStore(missing_column=True)
    assert eo.record_observations(store, org_id=ORG, entity_row_id="e1", message=_message(), observations=_OBS, settings=ON) == 1
    assert store.attempts == 2 and "source_connector_id" not in store.rows[0]


def test_feed_passes_the_events_connector_to_the_observation(_hubspot, monkeypatch):  # noqa: F811
    from app.services import customer_observation_feed as feed

    seen: list[Any] = []

    async def fake_observe(client, settings, **kw):
        seen.append(kw)
        return {"written": 1}

    monkeypatch.setattr(eo, "observe_customer_message", fake_observe)
    bound = [{"org_id": ORG, "system": "hubspot", "resource_type": "company", "resource_id": "co1", "entity_id": "e1"}]
    feed.handle_customer_message(_FeedClient(bound), _feed_event(), SimpleNamespace(entity_observations_enabled=True))
    assert seen[0]["message"].connector_id == "c1"
