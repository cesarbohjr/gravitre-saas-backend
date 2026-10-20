"""HubSpot webhook tenant routing: only live connectors, never an ambiguous portal."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.hubspot_trigger_service import find_hubspot_connector_by_portal


class _PagedConnectors:
    """``connectors`` select that honours ``.range()`` like PostgREST (row cap per page)."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.ranges: list[tuple[int, int]] = []
        self.filters: list[tuple] = []

    def table(self, name: str) -> _PagedConnectors:
        assert name == "connectors"
        return self

    def select(self, *_a) -> _PagedConnectors:
        return self

    def eq(self, col: str, val) -> _PagedConnectors:
        self.filters.append(("eq", col, val))
        return self

    def is_(self, col: str, val) -> _PagedConnectors:
        self.filters.append(("is", col, val))
        return self

    def order(self, col: str, *_a, **_k) -> _PagedConnectors:
        self.filters.append(("order", col))
        return self

    def range(self, start: int, end: int) -> _PagedConnectors:
        self.ranges.append((start, end))
        self._page = self.rows[start : end + 1]
        return self

    def execute(self) -> MagicMock:
        return MagicMock(data=self._page)


def _client(rows: list[dict]) -> _PagedConnectors:
    return _PagedConnectors(rows)


def _row(cid: str, org: str, *, status: str = "connected", deleted_at: str | None = None, hub_id=123) -> dict:
    return {
        "id": cid,
        "org_id": org,
        "type": "hubspot",
        "status": status,
        "deleted_at": deleted_at,
        "config": {"hub_id": hub_id},
    }


def test_live_connector_matches() -> None:
    found = find_hubspot_connector_by_portal(_client([_row("c-1", "org-1")]), 123)
    assert found is not None and found["id"] == "c-1"


def test_deleted_connector_is_ignored() -> None:
    rows = [_row("c-old", "org-old", deleted_at="2026-09-01T00:00:00Z"), _row("c-1", "org-1")]
    found = find_hubspot_connector_by_portal(_client(rows), 123)
    assert found is not None and found["id"] == "c-1"
    assert find_hubspot_connector_by_portal(_client(rows[:1]), 123) is None


def test_disconnected_connector_is_ignored() -> None:
    rows = [_row("c-off", "org-1", status="disconnected"), _row("c-err", "org-1", status="failed")]
    assert find_hubspot_connector_by_portal(_client(rows), 123) is None


def test_same_portal_in_two_orgs_does_not_fire() -> None:
    rows = [_row("c-1", "org-1"), _row("c-2", "org-2")]
    assert find_hubspot_connector_by_portal(_client(rows), "123") is None


def test_same_org_multiple_connectors_still_routes() -> None:
    rows = [_row("c-1", "org-1"), _row("c-2", "org-1", status="active")]
    found = find_hubspot_connector_by_portal(_client(rows), 123)
    assert found is not None and found["org_id"] == "org-1"


def _filler(n: int) -> list[dict]:
    return [_row(f"c-fill-{i:05d}", f"org-fill-{i}", hub_id=900000 + i) for i in range(n)]


def test_match_past_the_first_thousand_rows_is_found() -> None:
    client = _client(_filler(2500) + [_row("c-late", "org-late")])
    found = find_hubspot_connector_by_portal(client, 123)
    assert found is not None and found["id"] == "c-late"
    assert client.ranges == [(0, 999), (1000, 1999), (2000, 2999)]
    assert ("order", "id") in client.filters and ("eq", "type", "hubspot") in client.filters


def test_second_org_past_the_first_page_still_fails_closed() -> None:
    rows = [_row("c-1", "org-1")] + _filler(1500) + [_row("c-2", "org-2")]
    assert find_hubspot_connector_by_portal(_client(rows), 123) is None
