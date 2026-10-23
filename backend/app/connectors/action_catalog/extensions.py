"""Optional vendor catalog extensions — merge custom actions without editing core definitions."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.models import VendorCatalogSpec, ActionWorkflowSchema, WorkflowFieldSpec
from app.connectors.action_catalog.builder import action, build_vendor

# Static extensions are kept here so newly managed providers can ship without
# editing the generated core vendor_definitions module.
_FRESHSERVICE = build_vendor(
    "freshservice",
    "Freshservice",
    "Customer Support / ITSM",
    "https://api.freshservice.com/",
    shipped=True,
    department="support",
    v1=(
        action(
            "freshservice",
            "tickets.list",
            "List service tickets",
            tier="v1",
            kind="read",
            scope_suffix="tickets:read",
            api_reference="GET /api/v2/tickets",
            idempotent=True,
        ),
        action(
            "freshservice",
            "tickets.get",
            "Get service ticket",
            tier="v1",
            kind="read",
            scope_suffix="tickets:read",
            api_reference="GET /api/v2/tickets/{ticket_id}",
            idempotent=True,
        ),
    ),
    v2=(
        action(
            "freshservice",
            "tickets.update_status",
            "Update ticket status",
            tier="v2",
            kind="write",
            scope_suffix="tickets:write",
            api_reference="PUT /api/v2/tickets/{ticket_id}",
            requires_approval=True,
            input_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": ["string", "integer"]},
                    "status": {"type": ["string", "integer"]},
                    "connector_id": {"type": "string"},
                },
                "required": ["ticket_id", "status"],
                "additionalProperties": False,
            },
        ),
    ),
    v3=(
        action(
            "freshservice",
            "tickets.activities",
            "Get ticket activities",
            tier="v3",
            kind="read",
            scope_suffix="tickets:read",
            api_reference="GET /api/v2/tickets/{ticket_id}/activities",
            idempotent=True,
        ),
    ),
)

# Append org-specific or partner vendors here, or load from DB/MCP in a future release.
_OKTA = build_vendor(
    "okta",
    "Okta",
    "Security / Identity",
    "https://developer.okta.com/",
    shipped=True,
    department="security",
    v1=(
        action(
            "okta",
            "system_logs.list",
            "List Okta system log events",
            tier="v1",
            kind="read",
            scope_suffix="logs:read",
            api_reference="GET /api/v1/logs",
            idempotent=True,
            input_schema={
                "type": "object",
                "properties": {
                    "since": {"type": "string"},
                    "until": {"type": "string"},
                    "filter": {"type": "string"},
                    "q": {"type": "string"},
                    "limit": {"type": "integer"},
                    "sortOrder": {"type": "string"},
                    "connector_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        action(
            "okta",
            "users.get",
            "Get Okta user",
            tier="v1",
            kind="read",
            scope_suffix="users:read",
            api_reference="GET /api/v1/users/{user_id}",
            idempotent=True,
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "connector_id": {"type": "string"},
                },
                "required": ["user_id"],
                "additionalProperties": False,
            },
        ),
    ),
    v2=(
        action(
            "okta", "users.suspend", "Suspend compromised Okta user",
            tier="v2", kind="write", scope_suffix="users:manage", requires_approval=True,
            api_reference="POST /api/v1/users/{user_id}/lifecycle/suspend",
            workflow_schema=ActionWorkflowSchema(
                intent_label="Suspend an explicitly selected compromised Okta account",
                known_defaults=(("Target status", "SUSPENDED"),),
                required_fields=(WorkflowFieldSpec("target Okta user ID", ("user_id",), sensitive=True, inferrable=False),),
            ),
            input_schema={"type": "object", "properties": {
                "user_id": {"type": "string", "minLength": 1},
                "status": {"type": "string", "const": "SUSPENDED", "default": "SUSPENDED"},
                "connector_id": {"type": "string"}},
                "required": ["user_id", "status"], "additionalProperties": False},
        ),
        action(
            "okta",
            "groups.list",
            "List Okta groups for identity and access investigation",
            tier="v2",
            kind="read",
            scope_suffix="groups:read",
            api_reference="GET /api/v1/groups",
            idempotent=True,
            input_schema={
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "filter": {"type": "string"},
                    "search": {"type": "string"},
                    "limit": {"type": "integer"},
                    "after": {"type": "string"},
                    "connector_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        action(
            "okta",
            "apps.list",
            "List Okta applications for access and exposure review",
            tier="v2",
            kind="read",
            scope_suffix="apps:read",
            api_reference="GET /api/v1/apps",
            idempotent=True,
            input_schema={
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "filter": {"type": "string"},
                    "limit": {"type": "integer"},
                    "after": {"type": "string"},
                    "connector_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
    ),
    v3=(
        action(
            "okta",
            "users.factors.list",
            "List enrolled Okta factors when investigating account security posture",
            tier="v3",
            kind="read",
            scope_suffix="users:read",
            api_reference="GET /api/v1/users/{user_id}/factors",
            idempotent=True,
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "connector_id": {"type": "string"},
                },
                "required": ["user_id"],
                "additionalProperties": False,
            },
        ),
    ),
)


from app.connectors.nango_registry import BUSINESS_CONNECTORS


def _business_catalog(row: dict[str, Any]) -> VendorCatalogSpec:
    # Do not generate demo write workflows for a read-only integration.
    properties = {"connector_id": {"type": "string"}}
    required: list[str] = []
    if row["vendor"] == "harvest":
        properties["harvest_account_id"] = {"type": "string", "pattern": "^[0-9]+$"}
        required.append("harvest_account_id")
    if row["vendor"] == "freshsales":
        properties["contact_id"] = {"type": "string", "pattern": "^[0-9]+$"}
        required.append("contact_id")
    read = action(row["vendor"], row["read_action"], row["description"], tier="v1", kind="read",
                  scope_suffix="read", api_reference="GET " + row["read_path"], idempotent=True,
                  input_schema={"type": "object", "properties": properties, "required": required,
                                "additionalProperties": False})
    return VendorCatalogSpec(vendor=row["vendor"], display_name=row["display_name"], category=row["category"],
                             api_docs_url=row["api_docs_url"], shipped=True, v1=(read,), v2=(), v3=(),
                             demo_workflows=())


VENDOR_CATALOG_EXTENSIONS: tuple[VendorCatalogSpec, ...] = (
    _FRESHSERVICE, _OKTA, *(_business_catalog(row) for row in BUSINESS_CONNECTORS)
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
