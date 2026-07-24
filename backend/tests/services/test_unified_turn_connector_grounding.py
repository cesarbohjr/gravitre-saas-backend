"""Tests for unified-turn connector grounding guards."""
from __future__ import annotations

from app.services.unified_turn_connector_grounding import (
    integrations_claimed_disconnected,
    unified_live_message_claims_false_disconnect,
)


def test_integrations_claimed_disconnected_parses_gmail():
    slugs = integrations_claimed_disconnected(
        "Gmail isn't Connected here. Connect it at /connectors."
    )
    assert "gmail" in slugs


def test_false_disconnect_when_gmail_connected():
    assert unified_live_message_claims_false_disconnect(
        "Gmail isn't Connected here. Connect it at /connectors.",
        ["gmail", "hubspot"],
    )


def test_no_false_disconnect_when_gmail_not_connected():
    assert not unified_live_message_claims_false_disconnect(
        "Gmail isn't Connected here. Connect it at /connectors.",
        ["hubspot"],
    )


def test_no_false_disconnect_for_unrelated_reply():
    assert not unified_live_message_claims_false_disconnect(
        "I can draft that for Stephanie. What's the purpose?",
        ["gmail"],
    )
