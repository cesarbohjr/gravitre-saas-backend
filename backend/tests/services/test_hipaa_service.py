"""STA-110: HIPAA BAA workflow and PHI controls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.hipaa_service import (
    CURRENT_BAA_VERSION,
    HipaaComplianceError,
    accept_baa,
    enforce_hipaa_for_tool_invoke,
    get_hipaa_status,
    is_hipaa_ready,
    set_hipaa_enabled,
)


def _chainable(data: list | None = None, *, count: int | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.insert.return_value = mock
    result = MagicMock(data=data or [], error=None)
    if count is not None:
        result.count = count
    mock.execute.return_value = result
    return mock


def _org_client(*, settings: dict | None = None, data_region: str = "us") -> MagicMock:
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "organizations":
            return _chainable([{"settings": settings or {}, "data_region": data_region}])
        if name == "connectors":
            return _chainable([], count=0)
        if name == "org_hipaa_baa_acceptances":
            return _chainable([])
        return _chainable([])

    client.table.side_effect = table_side_effect
    return client


@patch("app.services.hipaa_service.write_audit_event")
def test_get_hipaa_status_not_ready_without_baa(mock_audit):
    client = _org_client(settings={"enterprise": {"hipaa": {"enabled": False}}})
    status = get_hipaa_status(client, "org-1")
    assert status["hipaaReady"] is False
    assert status["baaAccepted"] is False
    assert status["dataRegion"] == "us"
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_is_hipaa_ready_when_enabled_baa_and_us(mock_audit):
    client = _org_client(
        settings={
            "enterprise": {
                "hipaa": {
                    "enabled": True,
                    "baaAcceptedAt": "2026-06-08T00:00:00+00:00",
                    "baaVersion": CURRENT_BAA_VERSION,
                }
            }
        },
        data_region="us",
    )
    assert is_hipaa_ready(client, "org-1") is True
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_is_hipaa_ready_false_for_eu_region(mock_audit):
    client = _org_client(
        settings={
            "enterprise": {
                "hipaa": {
                    "enabled": True,
                    "baaAcceptedAt": "2026-06-08T00:00:00+00:00",
                }
            }
        },
        data_region="eu",
    )
    assert is_hipaa_ready(client, "org-1") is False
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_accept_baa_records_settings_and_audit(mock_audit):
    stored_settings: dict = {}
    client = MagicMock()
    baa_table = _chainable([])

    def table_side_effect(name: str):
        if name == "organizations":
            org_table = _chainable([{"settings": stored_settings, "data_region": "us"}])

            def do_update(payload: dict):
                stored_settings.clear()
                stored_settings.update(payload.get("settings") or {})
                return org_table

            org_table.update.side_effect = do_update
            return org_table
        if name == "org_hipaa_baa_acceptances":
            return baa_table
        if name == "connectors":
            return _chainable([], count=0)
        return _chainable([])

    client.table.side_effect = table_side_effect
    status = accept_baa(client, org_id="org-1", actor_id="user-1")
    assert status["baaAccepted"] is True
    baa_table.insert.assert_called_once()
    mock_audit.assert_called_once()


@patch("app.services.hipaa_service.write_audit_event")
def test_set_hipaa_enabled_requires_baa(mock_audit):
    client = _org_client(settings={"enterprise": {"hipaa": {}}})
    with pytest.raises(ValueError, match="Business Associate Agreement"):
        set_hipaa_enabled(client, org_id="org-1", actor_id="user-1", enabled=True)
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_enforce_blocks_phi_sensitive_action_when_not_ready(mock_audit):
    client = _org_client(settings={"enterprise": {"hipaa": {"enabled": True}}})
    with pytest.raises(HipaaComplianceError, match="email.send"):
        enforce_hipaa_for_tool_invoke(client, "org-1", "email.send", None)
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_enforce_allows_sensitive_action_when_hipaa_not_enabled(mock_audit):
    client = _org_client(settings={})
    enforce_hipaa_for_tool_invoke(client, "org-1", "email.send", None)
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_enforce_blocks_phi_capable_connector_when_not_ready(mock_audit):
    client = MagicMock()
    org_table = _chainable([{"settings": {}, "data_region": "us"}])
    connector_table = _chainable([{"id": "conn-1", "phi_capable": True}])

    def table_side_effect(name: str):
        if name == "organizations":
            return org_table
        if name == "connectors":
            return connector_table
        return _chainable([], count=0)

    client.table.side_effect = table_side_effect
    with pytest.raises(HipaaComplianceError, match="PHI-capable"):
        enforce_hipaa_for_tool_invoke(client, "org-1", "hubspot.contacts.list", "conn-1")
    mock_audit.assert_not_called()


@patch("app.services.hipaa_service.write_audit_event")
def test_enforce_allows_when_hipaa_ready(mock_audit):
    client = _org_client(
        settings={
            "enterprise": {
                "hipaa": {
                    "enabled": True,
                    "baaAcceptedAt": "2026-06-08T00:00:00+00:00",
                }
            }
        },
    )
    enforce_hipaa_for_tool_invoke(client, "org-1", "email.send", None)
    mock_audit.assert_not_called()
