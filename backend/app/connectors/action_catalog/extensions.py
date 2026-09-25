"""Optional vendor catalog extensions — merge custom actions without editing core definitions."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.builder import action, build_vendor
from app.connectors.action_catalog.models import VendorCatalogSpec

# shipped=False — not a customer marketplace Enable surface.
VENDOR_CATALOG_EXTENSIONS: tuple[VendorCatalogSpec, ...] = (
    build_vendor(
        "browser_agent",
        "Browser agent",
        "Internal",
        "https://example.com/",
        shipped=False,
        department="operations",
        v1=(
            action(
                "browser_agent",
                "read",
                "Read a public web page",
                tier="v1",
                kind="read",
                scope_suffix="read",
                idempotent=True,
                description="Read a public HTTPS page when no connector API exists. Use when the user asks to open a public URL in a browser.",
            ),
        ),
        v2=(
            action(
                "browser_agent",
                "interact",
                "Fill or submit a public browser form",
                tier="v2",
                kind="write",
                scope_suffix="interact",
                destructive=True,
                requires_approval=True,
                description=(
                    "Fill or submit a public browser form after HMAC confirm. "
                    "Use when the user asks to fill the httpbin.org public form. "
                    "Never use for HubSpot or other API-native writes."
                ),
            ),
        ),
        v3=(),
    ),
)

# Runtime per-action schema overrides (partner SDK, MCP, admin API).
ACTION_SCHEMA_EXTENSIONS: dict[str, dict[str, Any]] = {}


def register_vendor_extension(spec: VendorCatalogSpec) -> None:
    """Runtime hook for MCP servers or admin APIs to append catalog entries."""
    global VENDOR_CATALOG_EXTENSIONS
    VENDOR_CATALOG_EXTENSIONS = (*VENDOR_CATALOG_EXTENSIONS, spec)
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
