"""Load partner connector packages from manifest.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.connectors.sdk.handlers import ToolExecutor
from app.connectors.sdk.manifest import ConnectorManifest, parse_manifest
from app.connectors.sdk.registry import register_partner_connector, wrap_handler


def load_manifest_file(path: str | Path) -> ConnectorManifest:
    """Load and validate manifest.json from disk."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return parse_manifest(data)


def register_from_manifest(
    manifest: ConnectorManifest | dict[str, Any],
    handlers: dict[str, ToolExecutor],
) -> ConnectorManifest:
    """Validate manifest and register handlers with the partner registry."""
    parsed = manifest if isinstance(manifest, ConnectorManifest) else parse_manifest(manifest)
    wrapped = {action_id: wrap_handler(parsed, action_id, fn) for action_id, fn in handlers.items()}
    register_partner_connector(parsed, wrapped)
    return parsed


def load_partner_package(
    package_dir: str | Path,
    handlers: dict[str, ToolExecutor],
) -> ConnectorManifest:
    """Load manifest.json from a partner package directory and register handlers."""
    manifest_path = Path(package_dir) / "manifest.json"
    parsed = load_manifest_file(manifest_path)
    return register_from_manifest(parsed, handlers)
