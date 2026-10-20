"""Knowledge › Memory shows the connector a memory came from, only when lineage exists.

Read-only and flag-safe: with MEMORY_SOURCE_LINEAGE_ENABLED off the candidate
list reads exactly what it read before (the lineage column may not exist yet).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.services.memory_promotion_service import MemoryPromotionService

ORG = "org-1"


class _Query:
    def __init__(self, rows: list[dict[str, Any]], log: list[str], table: str) -> None:
        self._rows = rows
        self._log = log
        self._table = table

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        self._log.append(self._table)
        return self

    def eq(self, key: str, value: Any) -> "_Query":
        self._rows = [r for r in self._rows if str(r.get(key)) == str(value)]
        return self

    def in_(self, key: str, values: list[Any]) -> "_Query":
        wanted = {str(v) for v in values}
        self._rows = [r for r in self._rows if str(r.get(key)) in wanted]
        return self

    def order(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def range(self, *_a: Any) -> "_Query":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=list(self._rows), count=len(self._rows))


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.reads: list[str] = []

    def table(self, name: str) -> _Query:
        return _Query(self.tables.get(name, []), self.reads, name)


def _tables() -> dict[str, list[dict[str, Any]]]:
    return {
        "memory_promotion_candidates": [
            {"id": "c1", "org_id": ORG, "source_table": "agent_memories", "source_id": "m1", "content": "Net 30"},
            {"id": "c2", "org_id": ORG, "source_table": "org_glossary_terms", "source_id": "g1", "content": "ARR"},
        ],
        "agent_memories": [{"id": "m1", "org_id": ORG, "source_connector_id": "conn-1"}],
        "connectors": [{"id": "conn-1", "org_id": ORG, "type": "hubspot", "name": "", "status": "active"}],
    }


def _service(lineage: bool, client: _Client) -> MemoryPromotionService:
    service = MemoryPromotionService(settings=SimpleNamespace(memory_source_lineage_enabled=lineage))
    service._client = lambda: client  # type: ignore[method-assign]
    return service


def test_lineage_off_reads_nothing_extra_and_names_nothing() -> None:
    client = _Client(_tables())
    out = _service(False, client).list_candidates(ORG)
    assert client.reads == ["memory_promotion_candidates"]
    assert all("sourceConnector" not in item for item in out["items"])


def test_lineage_on_names_the_connector_without_ids() -> None:
    client = _Client(_tables())
    out = _service(True, client).list_candidates(ORG)
    by_id = {item["id"]: item for item in out["items"]}
    assert by_id["c1"]["sourceConnector"] == {"name": "HubSpot", "type": "HubSpot", "connected": True}
    assert "sourceConnector" not in by_id["c2"]
    assert "conn-1" not in repr(by_id["c1"]["sourceConnector"])


def test_lineage_read_failure_shows_no_connector() -> None:
    client = _Client(_tables())

    def broken(name: str) -> _Query:
        if name == "agent_memories":
            raise RuntimeError("column does not exist")
        return _Query(_tables().get(name, []), client.reads, name)

    client.table = broken  # type: ignore[method-assign]
    out = _service(True, client).list_candidates(ORG)
    assert all("sourceConnector" not in item for item in out["items"])
