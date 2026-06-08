"""STA-120: Connector fixtures for digital twin."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.connector_fixture_service import (
    ConnectorFixtureError,
    lookup_connector_fixture,
    upsert_connector_fixture,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def test_lookup_connector_fixture_returns_latest():
    fixtures = _table(
        [
            {
                "id": "fix-1",
                "org_id": "org-1",
                "environment": "production",
                "connector_type": "hubspot",
                "action": "hubspot.search_contacts",
                "response": {"total": 2, "results": []},
                "updated_at": "2026-06-08T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = fixtures

    row = lookup_connector_fixture(
        client,
        org_id="org-1",
        connector_type="hubspot",
        action="hubspot.search_contacts",
        environment="production",
    )
    assert row is not None
    assert row["response"]["total"] == 2


def test_upsert_connector_fixture_inserts_when_missing():
    fixtures = _table([])
    fixtures.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "fix-1",
                "org_id": "org-1",
                "environment": "production",
                "connector_type": "hubspot",
                "action": "hubspot.create_contact",
                "label": None,
                "request_fingerprint": {},
                "response": {"id": "123"},
                "source_run_id": None,
                "created_at": "2026-06-08T00:00:00+00:00",
                "updated_at": "2026-06-08T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = fixtures

    result = upsert_connector_fixture(
        client,
        org_id="org-1",
        connector_type="hubspot",
        action="hubspot.create_contact",
        response={"id": "123"},
        actor_id="user-1",
    )
    assert result["connectorType"] == "hubspot"
    fixtures.insert.assert_called_once()


def test_upsert_connector_fixture_requires_response():
    client = MagicMock()
    with pytest.raises(ConnectorFixtureError, match="response payload"):
        upsert_connector_fixture(
            client,
            org_id="org-1",
            connector_type="hubspot",
            action="hubspot.create_contact",
            response={},
            actor_id="user-1",
        )
