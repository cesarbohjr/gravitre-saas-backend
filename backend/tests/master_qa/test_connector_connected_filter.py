"""ECO-005 / DEC-004: 'no connected tools' must never become 'all tools'."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def matrix(monkeypatch):
    from app.services import connector_execution_matrix as module
    entries = (
        SimpleNamespace(chat_executable=True, connector_id="hubspot", action_key="hubspot.contacts.search"),
        SimpleNamespace(chat_executable=True, connector_id="slack", action_key="slack.channels.list"),
        SimpleNamespace(chat_executable=False, connector_id="other", action_key="other.unimplemented"),
    )
    monkeypatch.setattr(module, "build_connector_execution_matrix", lambda: entries)
    return module


def test_explicit_empty_connected_integrations_is_fail_closed(matrix):
    assert matrix.chat_executable_entries(connected_integrations=[]) == []


def test_omitted_connection_filter_is_catalog_mode_not_tenant_access(matrix):
    entries = matrix.chat_executable_entries()
    assert [entry.connector_id for entry in entries] == ["hubspot", "slack"]


@pytest.mark.parametrize("connected, expected", [
    (["HubSpot"], ["hubspot"]),
    (["slack"], ["slack"]),
    (["hubspot", "slack"], ["hubspot", "slack"]),
    (["missing"], []),
    (["  "], []),
])
def test_connected_filter_only_returns_matching_implemented_actions(
        matrix, connected, expected):
    assert [e.connector_id for e in matrix.chat_executable_entries(
        connected_integrations=connected)] == expected
