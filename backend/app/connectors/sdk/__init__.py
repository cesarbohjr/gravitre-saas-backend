"""Gravitre Connector SDK — partner manifest + handler registration (STA-70)."""
from app.connectors.sdk.handlers import BaseConnectorHandler, ConnectorActionHandler, ToolExecutor
from app.connectors.sdk.loader import load_manifest_file, load_partner_package, register_from_manifest
from app.connectors.sdk.manifest import ConnectorManifest, parse_manifest
from app.connectors.sdk.registry import (
    clear_partner_registry,
    get_partner_executor,
    get_partner_manifest,
    list_partner_actions,
    register_partner_connector,
)

__all__ = [
    "BaseConnectorHandler",
    "ConnectorActionHandler",
    "ConnectorManifest",
    "ToolExecutor",
    "clear_partner_registry",
    "get_partner_executor",
    "get_partner_manifest",
    "list_partner_actions",
    "load_manifest_file",
    "load_partner_package",
    "parse_manifest",
    "register_from_manifest",
    "register_partner_connector",
]
