"""Tests for canonical connector availability service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.connector_availability_service import (
    evaluate_connector_availability,
    find_integration_availability,
    format_connector_blocking_message,
    list_executable_integrations,
)


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    base.update(overrides)
    return Settings(**base)


def _hubspot_row(**overrides) -> dict:
    row = {
        "id": "c-hubspot",
        "name": "HubSpot",
        "type": "hubspot",
        "vendor": "hubspot",
        "status": "healthy",
        "environment": "production",
    }
    row.update(overrides)
    return row


@patch("app.connectors.connector_availability_service.list_registered_actions", return_value=["hubspot.contacts.search"])
@patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected")
@patch("app.connectors.connector_availability_service.load_oauth_tokens")
@patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True)
def test_hubspot_connected_executable_for_contact_search(
    _configured,
    mock_tokens,
    _auth,
    _actions,
):
    mock_tokens.return_value = {"access_token": "tok", "scopes": ["crm.objects.contacts.read"]}
    availability = evaluate_connector_availability(
        MagicMock(),
        "org-1",
        _hubspot_row(),
        _settings(),
        force_live=True,
        action_key="hubspot.contacts.search",
    )
    assert availability["execution_available"] is True
    assert availability["token_valid"] is True
    assert availability["scopes_valid"] is True
    assert availability["display_status"] == "connected"


@patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected")
@patch("app.connectors.connector_availability_service.load_oauth_tokens")
@patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True)
def test_hubspot_partial_scopes_still_executable_without_action_key(
    _configured,
    mock_tokens,
    _auth,
):
    """STA-307: listing must not require full authorize scopes (companies/tickets/notes)."""
    mock_tokens.return_value = {
        "access_token": "tok",
        "scopes": [
            "oauth",
            "crm.objects.contacts.read",
            "crm.objects.contacts.write",
            "crm.objects.deals.read",
            "crm.objects.deals.write",
            "crm.lists.read",
            "crm.lists.write",
            "automation",
        ],
    }
    availability = evaluate_connector_availability(
        MagicMock(),
        "org-1",
        _hubspot_row(),
        _settings(),
        force_live=True,
        action_key=None,
    )
    assert availability["auth_status"] == "connected"
    assert availability["display_status"] == "connected"
    assert availability["scopes_valid"] is True
    assert availability["blocking_reason"] is None
    assert availability["execution_available"] is True


@patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="auth_expired")
@patch("app.connectors.connector_availability_service.load_oauth_tokens")
@patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True)
def test_hubspot_token_expired_message(_configured, mock_tokens, _auth):
    mock_tokens.return_value = {"access_token": "tok", "scopes": ["crm.objects.contacts.read"]}
    availability = evaluate_connector_availability(
        MagicMock(),
        "org-1",
        _hubspot_row(status="error"),
        _settings(),
        force_live=True,
        action_key="hubspot.contacts.search",
    )
    assert availability["execution_available"] is False
    assert availability["blocking_reason"] == "token_expired"
    message = format_connector_blocking_message("hubspot", availability, action_key="hubspot.contacts.search")
    assert "authentication has expired" in message.lower()


@patch("app.connectors.connector_availability_service.list_registered_actions", return_value=["hubspot.contacts.search"])
@patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected")
@patch("app.connectors.connector_availability_service.load_oauth_tokens")
@patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True)
def test_hubspot_missing_scope(_configured, mock_tokens, _auth, _actions):
    mock_tokens.return_value = {"access_token": "tok", "scopes": ["oauth"]}
    availability = evaluate_connector_availability(
        MagicMock(),
        "org-1",
        _hubspot_row(),
        _settings(),
        force_live=True,
        action_key="hubspot.contacts.search",
    )
    assert availability["execution_available"] is False
    assert availability["blocking_reason"] == "missing_scope"
    message = format_connector_blocking_message("hubspot", availability, action_key="hubspot.contacts.search")
    assert "missing scope" in message.lower() or "scopes are missing" in message.lower()


@patch("app.connectors.connector_availability_service.list_registered_actions", return_value=[])
@patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected")
@patch("app.connectors.connector_availability_service.load_oauth_tokens")
@patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True)
def test_hubspot_action_not_registered(_configured, mock_tokens, _auth, _actions):
    mock_tokens.return_value = {"access_token": "tok", "scopes": ["crm.objects.contacts.read"]}
    availability = evaluate_connector_availability(
        MagicMock(),
        "org-1",
        _hubspot_row(),
        _settings(),
        force_live=True,
        action_key="hubspot.contacts.search",
    )
    assert availability["execution_available"] is False
    assert availability["blocking_reason"] == "unsupported_action"


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_list_executable_integrations_uses_live_availability(mock_list):
    mock_list.return_value = [
        {"vendor": "hubspot", "execution_available": True},
        {"vendor": "slack", "execution_available": False},
    ]
    connected = list_executable_integrations(MagicMock(), "org-1", _settings(), force_live=True)
    assert connected == ["hubspot"]
    mock_list.assert_called_once()


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_connectors_and_chat_share_source_of_truth(mock_list):
    mock_list.return_value = [
        {
            "vendor": "hubspot",
            "execution_available": True,
            "display_status": "connected",
            "source_of_truth": "connector_availability_service",
        }
    ]
    item = find_integration_availability(MagicMock(), "org-1", "hubspot", _settings(), force_live=True)
    assert item is not None
    assert item["source_of_truth"] == "connector_availability_service"
    assert item["display_status"] == "connected"
