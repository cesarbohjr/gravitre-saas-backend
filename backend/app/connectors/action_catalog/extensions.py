"""Optional vendor catalog extensions — merge custom actions without editing core definitions."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.models import VendorCatalogSpec

# Append org-specific or partner vendors here, or load from DB/MCP in a future release.
VENDOR_CATALOG_EXTENSIONS: tuple[VendorCatalogSpec, ...] = ()

# Runtime per-action schema overrides (partner SDK, MCP, admin API).
ACTION_SCHEMA_EXTENSIONS: dict[str, dict[str, Any]] = {}


def register_vendor_extension(spec: VendorCatalogSpec) -> None:
    """Runtime hook for MCP servers or admin APIs to append catalog entries."""
    global VENDOR_CATALOG_EXTENSIONS
    VENDOR_CATALOG_EXTENSIONS = (*VENDOR_CATALOG_EXTENSIONS, spec)
    from app.connectors.action_catalog.registry import get_vendor_catalog

    get_vendor_catalog.cache_clear()
    _invalidate_schema_caches()


def unregister_vendor_extension(vendor: str) -> None:
    """Remove one runtime vendor extension and invalidate derived catalog caches."""
    global VENDOR_CATALOG_EXTENSIONS
    before = len(VENDOR_CATALOG_EXTENSIONS)
    VENDOR_CATALOG_EXTENSIONS = tuple(
        spec for spec in VENDOR_CATALOG_EXTENSIONS if spec.vendor != vendor
    )
    if len(VENDOR_CATALOG_EXTENSIONS) != before:
        from app.connectors.action_catalog.registry import get_vendor_catalog

        get_vendor_catalog.cache_clear()
        _invalidate_schema_caches()


def register_action_schema(action_key: str, schema: dict[str, Any]) -> None:
    """Register or replace JSON Schema for a single action (future/partner connectors)."""
    ACTION_SCHEMA_EXTENSIONS[action_key] = schema
    _invalidate_schema_caches()


def register_action_schemas(schemas: dict[str, dict[str, Any]]) -> None:
    """Bulk-register action schemas from a partner manifest or MCP discovery."""
    ACTION_SCHEMA_EXTENSIONS.update(schemas)
    _invalidate_schema_caches()


def unregister_action_schemas(action_keys: list[str] | tuple[str, ...] | set[str]) -> None:
    """Remove runtime action schemas and invalidate derived schema caches."""
    changed = False
    for action_key in action_keys:
        if ACTION_SCHEMA_EXTENSIONS.pop(str(action_key), None) is not None:
            changed = True
    if changed:
        _invalidate_schema_caches()


def _invalidate_schema_caches() -> None:
    from app.connectors.action_catalog.action_parameters import (
        clear_action_schema_cache,
        clear_catalog_schema_cache,
    )

    clear_catalog_schema_cache()
    clear_action_schema_cache()


def merge_catalog_extensions(base: dict[str, VendorCatalogSpec]) -> dict[str, VendorCatalogSpec]:
    merged = dict(base)
    for spec in VENDOR_CATALOG_EXTENSIONS:
        if spec.vendor in merged:
            continue
        merged[spec.vendor] = spec
    return merged
