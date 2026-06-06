"""Connector SDK manifest validation tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.connectors.sdk.manifest import ConnectorManifest, parse_manifest

EXAMPLE_MANIFEST = Path(__file__).resolve().parents[4] / "docs/integration/examples/acme-tools/manifest.json"


def test_parse_example_manifest():
    data = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    manifest = parse_manifest(data)
    assert manifest.vendor == "acme_tools"
    assert manifest.action_keys() == ["acme_tools.tickets.list", "acme_tools.tickets.create"]
    assert manifest.scopes_for_action("acme_tools.tickets.list") == [
        "acme_tools:tickets:read",
        "acme_tools:*",
    ]


def test_rejects_unsupported_manifest_version():
    with pytest.raises(ValidationError):
        parse_manifest(
            {
                "manifestVersion": "2.0",
                "id": "com.test",
                "name": "Test",
                "version": "1.0.0",
                "vendor": "test",
                "auth": {"type": "apiKey"},
            }
        )


def test_rejects_actions_capability_without_actions():
    with pytest.raises(ValidationError):
        parse_manifest(
            {
                "manifestVersion": "1.0",
                "id": "com.test",
                "name": "Test",
                "version": "1.0.0",
                "vendor": "test_vendor",
                "auth": {"type": "apiKey"},
                "capabilities": ["actions"],
                "actions": [],
            }
        )


def test_oauth_auth_config():
    manifest = ConnectorManifest.model_validate(
        {
            "manifestVersion": "1.0",
            "id": "com.oauth",
            "name": "OAuth Test",
            "version": "1.0.0",
            "vendor": "oauth_test",
            "auth": {
                "type": "oauth2",
                "authorizationUrl": "https://example.com/auth",
                "tokenUrl": "https://example.com/token",
                "scopes": ["read"],
            },
            "capabilities": ["triggers"],
            "triggers": [{"id": "event.received", "name": "Event"}],
        }
    )
    assert manifest.auth.type == "oauth2"
