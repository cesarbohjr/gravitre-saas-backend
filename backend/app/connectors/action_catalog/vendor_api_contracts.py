"""Pinned vendor HTTP contracts for ActionSpec drift detection.

CI compares stored ``action_parameters`` / executors against these snapshots
sourced from vendor OpenAPI (not inferred). Update when vendors change their API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

APOLLO_OPENAPI_URL = "https://docs.apollo.io/openapi/apollo-rest-api.json"


@dataclass(frozen=True)
class VendorHttpContract:
    """Minimal invoke contract for one catalog action."""

    action_key: str
    method: str
    path: str
    required_body_fields: tuple[str, ...]
    optional_body_fields: tuple[str, ...] = ()
    field_enums: dict[str, tuple[str, ...]] | None = None
    openapi_operation_id: str | None = None
    docs_url: str | None = None
    vendor: str = "apollo"
    source: str = "apollo-openapi-2026-07-28"


# Apollo POST /labels — Create a List (operationId: create-a-list)
# https://docs.apollo.io/reference/create-a-list
APOLLO_LISTS_CREATE_CONTRACT = VendorHttpContract(
    action_key="apollo.lists.create",
    method="POST",
    path="/labels",
    required_body_fields=("name", "modality"),
    optional_body_fields=("book_of_business",),
    field_enums={"modality": ("contacts", "accounts")},
    openapi_operation_id="create-a-list",
    docs_url="https://docs.apollo.io/reference/create-a-list",
)

VENDOR_HTTP_CONTRACTS: dict[str, VendorHttpContract] = {
    APOLLO_LISTS_CREATE_CONTRACT.action_key: APOLLO_LISTS_CREATE_CONTRACT,
}


def contract_for_action(action_key: str) -> VendorHttpContract | None:
    return VENDOR_HTTP_CONTRACTS.get(action_key.strip().lower())


def catalog_schema_required_fields(action_key: str) -> set[str]:
    from app.connectors.action_catalog.action_parameters import resolve_action_schema

    vendor, _, suffix = action_key.partition(".")
    if not suffix:
        return set()
    schema = resolve_action_schema(action_key, kind="write", suffix=suffix.split(".")[-1])
    required = schema.get("required") or []
    out = {str(f) for f in required if str(f).strip()}
    for branch in schema.get("anyOf") or []:
        if isinstance(branch, dict):
            for field in branch.get("required") or []:
                out.add(str(field))
    return out


def catalog_schema_properties(action_key: str) -> set[str]:
    from app.connectors.action_catalog.action_parameters import resolve_action_schema

    _, _, suffix = action_key.partition(".")
    schema = resolve_action_schema(action_key, kind="write", suffix=suffix.split(".")[-1])
    props = schema.get("properties") or {}
    return {str(k) for k in props.keys() if k != "connector_id"}


def drift_report(action_key: str) -> list[str]:
    """Return human-readable drift messages; empty when catalog matches vendor contract."""
    contract = contract_for_action(action_key)
    if contract is None:
        return []
    issues: list[str] = []
    catalog_required = catalog_schema_required_fields(action_key)
    vendor_required = set(contract.required_body_fields)
    missing_in_catalog = vendor_required - catalog_required
    # name may be satisfied via list_name alias — treat either as covering name.
    if "name" in missing_in_catalog and "list_name" in catalog_required:
        missing_in_catalog.discard("name")
    if missing_in_catalog:
        issues.append(
            f"{action_key}: catalog schema missing vendor-required fields {sorted(missing_in_catalog)}"
        )
    catalog_props = catalog_schema_properties(action_key)
    vendor_props = set(contract.required_body_fields) | set(contract.optional_body_fields)
    extra = catalog_props - vendor_props - {"list_name", "payload"}
    if extra:
        issues.append(
            f"{action_key}: catalog properties not in vendor contract: {sorted(extra)}"
        )
    if contract.field_enums:
        from app.connectors.action_catalog.action_parameters import resolve_action_schema

        _, _, suffix = action_key.partition(".")
        schema = resolve_action_schema(action_key, kind="write", suffix=suffix.split(".")[-1])
        props = schema.get("properties") or {}
        for field, allowed in contract.field_enums.items():
            spec = props.get(field) if isinstance(props.get(field), dict) else {}
            enum_vals = tuple(spec.get("enum") or ())
            if enum_vals and tuple(enum_vals) != allowed:
                issues.append(
                    f"{action_key}: {field} enum {enum_vals} != vendor {allowed}"
                )
    return issues
