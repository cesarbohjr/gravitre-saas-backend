"""Regression tests for deterministic connector status answers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.connector_status_reply_service import (
    ConnectorConnectionState,
    ConnectorStatusQuestionKind,
    answer_connector_status_question,
    format_connected_list_answer,
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
        ("is Apollo connected.", ConnectorStatusQuestionKind.CONNECTION, "apollo"),
        ("Can you check whether Apollo is connected?", ConnectorStatusQuestionKind.CONNECTION, "apollo"),
        ("What is the status of Apollo?", ConnectorStatusQuestionKind.CONNECTION, "apollo"),
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


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_connected_healthy(mock_list):
    mock_list.return_value = (
        [
        _availability_row(
            vendor="hubspot",
            execution_available=True,
            auth_status="connected",
            display_status="connected",
            health_status="healthy",
            connected=True,
        )
        ],
        False,
    )
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


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_not_connected_but_supported(mock_list):
    mock_list.return_value = (
        [
            _availability_row(vendor="hubspot", execution_available=True, auth_status="connected", display_status="connected", connected=True),
        ],
        False,
    )
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


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_unsupported_connector(mock_list):
    mock_list.return_value = ([], False)
    result = answer_connector_status_question(
        "Is SomeUnknownPlatform connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
        connected_integrations=["hubspot"],
    )
    assert result is not None
    assert "doesn't currently support" in result.text


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_degraded_connection(mock_list):
    mock_list.return_value = (
        [
        _availability_row(
            vendor="clay",
            execution_available=False,
            auth_status="connected",
            display_status="error",
            health_status="error",
            connected=True,
        )
        ],
        False,
    )
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert result.text == "Clay is connected, but the connection needs attention."


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_auth_expired(mock_list):
    mock_list.return_value = (
        [
        _availability_row(
            vendor="clay",
            execution_available=False,
            auth_status="auth_expired",
            display_status="error",
            blocking_reason="token_expired",
            connected=False,
        )
        ],
        False,
    )
    result = answer_connector_status_question(
        "Is Clay connected?",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    assert result is not None
    assert result.text == "Clay is configured, but its authentication has expired."


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_service_failure_unknown(mock_list):
    mock_list.return_value = (None, True)
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


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_connected_list_question(mock_list):
    mock_list.return_value = (
        [
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
        ],
        False,
    )
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


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_support_question(mock_list):
    mock_list.return_value = (
        [
            _availability_row(vendor="hubspot", execution_available=True, auth_status="connected", display_status="connected", connected=True),
        ],
        False,
    )
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
    assert is_connector_status_question("is Apollo connected.") is True
    assert is_connector_status_question("Create a HubSpot contact") is False


def test_format_connection_answer_unsupported():
    text = format_connection_answer(
        vendor_slug="someunknownplatform",
        state=ConnectorConnectionState.UNSUPPORTED,
        supported=False,
    )
    assert "doesn't currently support" in text


# Confirmed live incident, retrieval A, 2026-09-21T15:25:18Z, org f07e57c0…
# text_head: "You have Apollo, Google Ads, Google Search Console, and Hubspot connected."
# tool_names: []  — no getConnectorStatus.
RETRIEVAL_AB_A_MESSAGE = "What connectors are connected? (retrieval-ab A 202609211525)"
RETRIEVAL_AB_A_SLUGS = ["apollo", "google_ads", "google_search_console", "hubspot"]
RETRIEVAL_AB_A_FALSE_CLAIM = (
    "You have Apollo, Google Ads, Google Search Console, and Hubspot connected."
)


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_retrieval_ab_a_slug_list_is_not_a_connector_status_claim(mock_rows):
    """Routing slugs must not become an itemized connected list when the live check fails."""
    mock_rows.return_value = (None, True)
    result = answer_connector_status_question(
        RETRIEVAL_AB_A_MESSAGE,
        client=MagicMock(),
        org_id="f07e57c0-1501-4000-8000-c04e57a00001",
        settings=MagicMock(),
        connected_integrations=RETRIEVAL_AB_A_SLUGS,
    )
    assert result is not None
    assert result.text != RETRIEVAL_AB_A_FALSE_CLAIM
    assert "Apollo" not in result.text
    assert "Google Ads" not in result.text
    assert "Google Search Console" not in result.text
    assert "Hubspot" not in result.text
    assert "couldn't verify" in result.text
    assert result.source == "unverified"


@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
def test_retrieval_ab_a_list_names_only_getconnectorstatus_executable_rows(mock_rows):
    """A named list is allowed only from getConnectorStatus rows with execution_available."""
    mock_rows.return_value = (
        [
            _availability_row(vendor="hubspot", execution_available=True, auth_status="connected", display_status="connected", connected=True),
            _availability_row(vendor="apollo", execution_available=False, auth_status="pending_auth", display_status="disconnected"),
            _availability_row(vendor="google_ads", execution_available=False, auth_status="pending_auth", display_status="disconnected"),
            _availability_row(vendor="google_search_console", execution_available=False, auth_status="auth_expired", display_status="error"),
        ],
        False,
    )
    result = answer_connector_status_question(
        RETRIEVAL_AB_A_MESSAGE,
        client=MagicMock(),
        org_id="f07e57c0-1501-4000-8000-c04e57a00001",
        settings=MagicMock(),
        connected_integrations=RETRIEVAL_AB_A_SLUGS,
    )
    assert result is not None
    assert result.source == "getConnectorStatus"
    assert result.text == "You have Hubspot connected."
    assert result.text != RETRIEVAL_AB_A_FALSE_CLAIM
    mock_rows.assert_called_once()


def test_retrieval_ab_a_format_ignores_routing_slugs():
    text = format_connected_list_answer(None, connected_slugs=RETRIEVAL_AB_A_SLUGS)
    assert text != RETRIEVAL_AB_A_FALSE_CLAIM
    assert "Apollo" not in text


def test_retrieval_ab_a_fast_route_is_simple():
    """The live probe requires routing tier simple. Fast mode classifies this question that way."""
    from app.services.assistant_routing_tier import classify_routing_tier

    decision = classify_routing_tier(RETRIEVAL_AB_A_MESSAGE, mode="fast")
    assert decision.tier == "simple"


def test_retrieval_ab_a_shortcut_emits_getconnectorstatus_tool_name():
    from app.operators.assistant_sse import sse_react_tool_start

    event = sse_react_tool_start(
        call_id="retrieval-ab-a",
        registry_tool_name="assistant_connector_status",
        tool_args={"org_id": "f07e57c0-1501-4000-8000-c04e57a00001"},
    )
    assert event.sse_type == "tool-input-available"
    assert event.payload["toolName"] == "getConnectorStatus"
