"""HubSpot webhook tenant routing: only live connectors, never an ambiguous portal."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.hubspot_trigger_service import find_hubspot_connector_by_portal


def _client(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=rows)
    return client


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
