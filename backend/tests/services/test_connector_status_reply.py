"""Regression tests for deterministic connector status answers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.connector_status_reply_service import (
    ConnectorConnectionState,
    ConnectorStatusQuestionKind,
    answer_connector_status_question,
    format_connection_answer,
    is_connector_status_question,
    parse_connector_status_question,
    resolve_connector_slug_from_text,
)
from app.services.response_composer import looks_like_raw_backend
from app.services.user_facing_copy_guard import finalize_user_facing_message


def _availability_row(
    *,
    vendor: str,
    execution_available: bool = False,
    auth_status: str | None = None,
    display_status: str = "disconnected",
    health_status: str = "disconnected",
    blocking_reason: str | None = None,
    connected: bool = False,
) -> dict:
    return {
        "vendor": vendor,
        "execution_available": execution_available,
        "auth_status": auth_status,
        "display_status": display_status,
        "health_status": health_status,
        "blocking_reason": blocking_reason,
        "connected": connected,
    }


@pytest.mark.parametrize(
    ("message", "kind", "slug"),
    [
        ("Is HubSpot connected?", ConnectorStatusQuestionKind.CONNECTION, "hubspot"),
        ("Is Clay connected?", ConnectorStatusQuestionKind.CONNECTION, "clay"),
        ("Is GA4 connected?", ConnectorStatusQuestionKind.CONNECTION, "google_analytics"),
        ("Does Gravitre support Clay?", ConnectorStatusQuestionKind.SUPPORT, "clay"),
        (
            "What connectors do I have connected?",
            ConnectorStatusQuestionKind.LIST,
            None,
        ),
    ],
)
def test_parse_connector_status_question(message, kind, slug):
    parsed = parse_connector_status_question(message)
    assert parsed is not None
    assert parsed.kind == kind
    assert parsed.vendor_slug == slug


def test_resolve_ga4_alias():
    assert resolve_connector_slug_from_text("Is GA4 connected?") == "google_analytics"


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_connected_healthy(mock_list):
    mock_list.return_value = [
        _availability_row(
            vendor="hubspot",
            execution_available=True,
            auth_status="connected",
            display_status="connected",
            health_status="healthy",
            connected=True,
        )
    ]
    result = answer_connector_status_question(
        "Is HubSpot connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
        connected_integrations=["hubspot"],
    )
    assert result is not None
    assert "Yes, Hubspot is connected and healthy." == result.text
    assert "assistant_" not in result.text.lower()


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_not_connected_but_supported(mock_list):
    mock_list.return_value = [
        _availability_row(vendor="hubspot", execution_available=True, auth_status="connected", display_status="connected", connected=True),
    ]
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
        connected_integrations=["hubspot"],
    )
    assert result is not None
    assert result.text.startswith("No, Clay isn't connected to your Gravitre account.")
    assert "assistant_connector_status" not in result.text


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_unsupported_connector(mock_list):
    mock_list.return_value = []
    result = answer_connector_status_question(
        "Is SomeUnknownPlatform connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
        connected_integrations=["hubspot"],
    )
    assert result is not None
    assert "doesn't currently support" in result.text


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_degraded_connection(mock_list):
    mock_list.return_value = [
        _availability_row(
            vendor="clay",
            execution_available=False,
            auth_status="connected",
            display_status="error",
            health_status="error",
            connected=True,
        )
    ]
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert result.text == "Clay is connected, but the connection needs attention."


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_auth_expired(mock_list):
    mock_list.return_value = [
        _availability_row(
            vendor="clay",
            execution_available=False,
            auth_status="auth_expired",
            display_status="error",
            blocking_reason="token_expired",
            connected=False,
        )
    ]
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert result.text == "Clay is configured, but its authentication has expired."


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_service_failure_unknown(mock_list):
    mock_list.side_effect = RuntimeError("timeout")
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
        connected_integrations=["hubspot"],
    )
    assert result is not None
    assert result.text == "I couldn't verify Clay's connection status right now."
    assert "isn't connected" not in result.text.lower()


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_connected_list_question(mock_list):
    mock_list.return_value = [
        _availability_row(
            vendor="hubspot",
            execution_available=True,
            auth_status="connected",
            display_status="connected",
            connected=True,
        ),
        _availability_row(
            vendor="gmail",
            execution_available=True,
            auth_status="connected",
            display_status="connected",
            connected=True,
        ),
    ]
    result = answer_connector_status_question(
        "What connectors do I have connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert "Gmail" in result.text
    assert "Hubspot" in result.text
    assert "schema" not in result.text.lower()


@patch("app.connectors.connector_availability_service.list_connector_availability")
def test_support_question(mock_list):
    mock_list.return_value = [
        _availability_row(vendor="hubspot", execution_available=True, auth_status="connected", display_status="connected", connected=True),
    ]
    result = answer_connector_status_question(
        "Does Gravitre support Clay?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert "available as an integration" in result.text
    assert "connected to your account" in result.text


def test_internal_language_guard():
    leaky = (
        "I don't have the connector status for Clay. I'd need assistant_connector_status "
        "to verify and the org list only names Apollo."
    )
    assert looks_like_raw_backend(leaky) is True
    cleaned = finalize_user_facing_message(leaky)
    assert "assistant_connector_status" not in cleaned.lower()
    assert "function" not in cleaned.lower() or "assistant" not in cleaned.lower()


def test_is_connector_status_question():
    assert is_connector_status_question("Is Clay connected?") is True
    assert is_connector_status_question("Create a HubSpot contact") is False


def test_format_connection_answer_unsupported():
    text = format_connection_answer(
        vendor_slug="someunknownplatform",
        state=ConnectorConnectionState.UNSUPPORTED,
        supported=False,
    )
    assert "doesn't currently support" in text
