"""Partner connector registry — loads manifests and registers invoke_tool executors."""
from __future__ import annotations

import logging
from typing import Any

from app.connectors.sdk.handlers import ToolExecutor
from app.connectors.sdk.manifest import ConnectorManifest, parse_manifest
from app.services.agent_tool_permissions import ACTION_REQUIRED_SCOPES
from app.services.tool_types import ToolContext, ToolValidationError

logger = logging.getLogger(__name__)

_PARTNER_EXECUTORS: dict[str, ToolExecutor] = {}
_PARTNER_MANIFESTS: dict[str, ConnectorManifest] = {}
_VENDOR_BY_ACTION: dict[str, str] = {}


def register_partner_connector(
    manifest: ConnectorManifest,
    handlers: dict[str, ToolExecutor],
) -> None:
    """Register a partner connector package.

    ``handlers`` maps action id (e.g. ``tickets.list``) to executor callables.
  Canonical invoke_tool keys are ``{vendor}.{action_id}``.
    """
    expected = {action.id: manifest.vendor for action in manifest.actions}
    for action_id, vendor in expected.items():
        if action_id not in handlers:
            raise ValueError(f"manifest declares action {action_id!r} but no handler was provided")
        action_key = f"{vendor}.{action_id}"
        if action_key in _PARTNER_EXECUTORS:
            raise ValueError(f"action already registered: {action_key}")
        _PARTNER_EXECUTORS[action_key] = handlers[action_id]
        _VENDOR_BY_ACTION[action_key] = vendor
        scopes = manifest.scopes_for_action(action_key)
        ACTION_REQUIRED_SCOPES[action_key] = scopes

    _PARTNER_MANIFESTS[manifest.vendor] = manifest

    from app.connectors.action_catalog.extensions import register_action_schemas

    partner_schemas: dict[str, dict] = {}
    for action in manifest.actions:
        if action.input_schema:
            partner_schemas[f"{manifest.vendor}.{action.id}"] = action.input_schema
    if partner_schemas:
        register_action_schemas(partner_schemas)

    logger.info(
        "registered partner connector vendor=%s version=%s actions=%s",
        manifest.vendor,
        manifest.version,
        manifest.action_keys(),
    )


def get_partner_executor(action: str) -> ToolExecutor | None:
    """Return a partner executor for a canonical action key, if registered."""
    return _PARTNER_EXECUTORS.get(action)


def list_partner_actions() -> list[str]:
    """List registered partner tool action keys."""
    return sorted(_PARTNER_EXECUTORS.keys())


def get_partner_manifest(vendor: str) -> ConnectorManifest | None:
    """Return a registered partner manifest by vendor slug."""
    return _PARTNER_MANIFESTS.get(vendor)


def clear_partner_registry() -> None:
    """Clear partner registrations (tests only)."""
    for action in list(_PARTNER_EXECUTORS.keys()):
        ACTION_REQUIRED_SCOPES.pop(action, None)
    _PARTNER_EXECUTORS.clear()
    _PARTNER_MANIFESTS.clear()
    _VENDOR_BY_ACTION.clear()


def wrap_handler(manifest: ConnectorManifest, action_id: str, handler: ToolExecutor) -> ToolExecutor:
    """Wrap a handler to enforce manifest vendor prefix on action results."""

    def _wrapped(ctx: ToolContext, params: dict[str, Any]) -> Any:
        action_key = f"{manifest.vendor}.{action_id}"
        result = handler(ctx, params)
        if hasattr(result, "action") and result.action != action_key:
            raise ToolValidationError(f"handler returned action {result.action!r}, expected {action_key!r}")
        return result

    return _wrapped
