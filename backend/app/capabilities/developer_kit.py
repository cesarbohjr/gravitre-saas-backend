"""First-party developer contract for Gravitre portable capability packages."""
from __future__ import annotations

from typing import Any

MANIFEST_SCHEMA_VERSION = "1"


def gravitre_plugin_template() -> dict[str, Any]:
    return {
        "schema": "gravitre-plugin",
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "name": "example-capability",
        "version": "0.1.0",
        "description": "Describe the business capability this package adds.",
        "license": "Apache-2.0",
        "publisher": "Example Publisher",
        "skills": ["skills/example"],
        "mcpServers": {
            "example": {
                "url": "https://mcp.example.com/sse",
                "transport": "sse",
                "auth": {"type": "bearer"},
            }
        },
        "connectors": [],
        "agents": [],
        "plays": [],
        "templates": [],
        "permissions": [],
    }


def developer_kit_contract() -> dict[str, Any]:
    return {
        "manifestSchema": "gravitre-plugin",
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "template": gravitre_plugin_template(),
        "supportedPortableActivation": {
            "skill": "lazy_context",
            "mcp": "admin_prepare_discover_enable",
            "connector": "existing_connector_oauth_or_credentials",
        },
        "declarationOnly": {
            "agent": "native adapter required",
            "play": "bind to a native Gravitre Play/workflow",
            "template": "native adapter required",
            "ui_extension": "native adapter required",
            "command": "inert metadata only",
            "hook": "inert metadata only",
        },
        "security": {
            "scriptsExecuteDirectly": False,
            "privateSigningKeysAccepted": False,
            "packageSignature": "Ed25519 detached signature verified against a supplied public key",
            "publisherTrust": "separate explicit org/platform trust decision",
            "writes": "canonical Gravitre approval and source-of-record verification",
        },
        "distribution": {
            "github": True,
            "zip": True,
            "marketplace": True,
            "mcp": True,
            "privateGithubUsesExistingConnector": True,
        },
    }
