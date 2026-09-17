"""F1 READ slice — build-time ActionSpec augmentation (not a runtime registry).

Ownership model (option B):
- Authoritative runtime object is the catalog ActionSpec on VendorCatalogSpec.
- This module fills EMPTY F1 fields at catalog construction, then stamps spec_revision.
- get_action_spec() returns that single materialized object.
- If vendor_definitions later sets the same fields, catalog values win.

Do not import _OVERLAYS from ReAct, workflow, or executors.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from functools import lru_cache
from typing import Any

from app.connectors.action_catalog.models import ActionSpec, ParameterSourceRule, VendorCatalogSpec
from app.connectors.action_catalog.tool_aliases import REGISTRY_VENDOR_PREFIX_ALIASES

# Catalog keys (ActionSpec.id) for the F1 cross-connector READ slice.
F1_CATALOG_ACTIONS: frozenset[str] = frozenset(
    {
        "google_analytics.reports.run",
        "google_search_console.searchAnalytics.query",
        "hubspot.deals.search",
        "quickbooks.invoices.list",
        "zendesk.tickets.list",
    }
)

_REVERSE_VENDOR = {alias: vendor for vendor, alias in REGISTRY_VENDOR_PREFIX_ALIASES.items()}


def catalog_action_key(action_key: str) -> str:
    """Map invoke_tool / alias keys onto catalog ActionSpec.id."""
    key = str(action_key or "").strip()
    if not key:
        return key
    vendor, _, rest = key.partition(".")
    catalog_vendor = _REVERSE_VENDOR.get(vendor)
    if catalog_vendor and rest:
        return f"{catalog_vendor}.{rest}"
    return key


def registry_action_key(action_key: str) -> str:
    """Map catalog ActionSpec.id onto invoke_tool registry keys when aliased."""
    key = str(action_key or "").strip()
    vendor, _, rest = key.partition(".")
    alias = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
    if alias and rest:
        return f"{alias}.{rest}"
    return key


def is_f1_read_action(action_key: str) -> bool:
    catalog = catalog_action_key(action_key)
    return catalog in F1_CATALOG_ACTIONS or str(action_key or "").strip() in F1_CATALOG_ACTIONS


def _rule(
    parameter: str,
    *sources: str,
    required_by_api: bool = False,
    required_from_user: bool = False,
    aliases: tuple[str, ...] = (),
    default: Any = None,
) -> ParameterSourceRule:
    return ParameterSourceRule(
        parameter=parameter,
        sources=tuple(sources),  # type: ignore[arg-type]
        required_by_api=required_by_api,
        required_from_user=required_from_user,
        aliases=aliases,
        default=default,
    )


_OVERLAYS: dict[str, dict[str, Any]] = {
    "google_analytics.reports.run": {
        "capabilities": ("analytics.traffic_overview", "analytics.query"),
        "required_parameters": ("property_id", "start_date", "end_date"),
        "optional_parameters": ("metrics", "dimensions", "connector_id"),
        "parameter_source_rules": (
            _rule(
                "property_id",
                "REFERENCE_STATE",
                "TASK_CONTEXT",
                "BUSINESS_IDENTITY",
                "RESOURCE_RESOLVER",
                "CONNECTOR_METADATA",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("propertyId", "property"),
            ),
            _rule(
                "start_date",
                "TIME_RESOLVER",
                "USER_EXPLICIT",
                "ACTION_DEFAULT",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("startDate",),
                default="30daysAgo",
            ),
            _rule(
                "end_date",
                "TIME_RESOLVER",
                "USER_EXPLICIT",
                "ACTION_DEFAULT",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("endDate",),
                default="today",
            ),
            _rule("metrics", "CAPABILITY_RECIPE", "ACTION_DEFAULT", "MODEL_INFERENCE", default=["activeUsers", "sessions"]),
            _rule("dimensions", "CAPABILITY_RECIPE", "MODEL_INFERENCE"),
        ),
        "resource_requirements": ("property",),
        "auth_scope_requirements": ("google_analytics:read", "google_analytics:*"),
        "provider_constraints": {"date_order": "start_lte_end", "resource_type": "ga4_property"},
        "availability_requirements": ("connector_connected", "auth_valid", "resource_resolved"),
        "governance_classification": "read",
        "execution_adapter": "analytics.reports.run",
        "observation_adapter": "ga4_read_observation",
    },
    "google_search_console.searchAnalytics.query": {
        "capabilities": ("search.performance", "analytics.traffic_overview"),
        "required_parameters": ("site_url", "start_date", "end_date"),
        "optional_parameters": ("dimensions", "row_limit", "connector_id"),
        "parameter_source_rules": (
            _rule(
                "site_url",
                "REFERENCE_STATE",
                "TASK_CONTEXT",
                "BUSINESS_IDENTITY",
                "RESOURCE_RESOLVER",
                "CONNECTOR_METADATA",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("siteUrl", "site"),
            ),
            _rule(
                "start_date",
                "TIME_RESOLVER",
                "USER_EXPLICIT",
                "ACTION_DEFAULT",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("startDate",),
                default="28daysAgo",
            ),
            _rule(
                "end_date",
                "TIME_RESOLVER",
                "USER_EXPLICIT",
                "ACTION_DEFAULT",
                "MODEL_INFERENCE",
                required_by_api=True,
                aliases=("endDate",),
                default="today",
            ),
            _rule("dimensions", "CAPABILITY_RECIPE", "ACTION_DEFAULT", "MODEL_INFERENCE", default=["page"]),
            _rule("row_limit", "USER_EXPLICIT", "ACTION_DEFAULT", "MODEL_INFERENCE", aliases=("rowLimit",), default=25),
        ),
        "resource_requirements": ("site",),
        "auth_scope_requirements": ("google_search_console:read", "google_search_console:*"),
        "provider_constraints": {"date_order": "start_lte_end", "resource_type": "gsc_site"},
        "availability_requirements": ("connector_connected", "auth_valid", "resource_resolved"),
        "governance_classification": "read",
        "execution_adapter": "searchconsole.searchAnalytics.query",
        "observation_adapter": "gsc_read_observation",
    },
    "hubspot.deals.search": {
        "capabilities": ("crm.deals.read",),
        "required_parameters": (),
        "optional_parameters": ("query", "filter_groups", "limit", "connector_id"),
        "parameter_source_rules": (
            _rule("portal_id", "RESOURCE_RESOLVER", "CONNECTOR_METADATA", aliases=("portalId", "hub_id")),
            _rule("query", "USER_EXPLICIT", "TASK_CONTEXT", "MODEL_INFERENCE"),
            _rule("filter_groups", "USER_EXPLICIT", "MODEL_INFERENCE", aliases=("filterGroups",)),
            _rule("limit", "USER_EXPLICIT", "ACTION_DEFAULT", "MODEL_INFERENCE", default=25),
        ),
        "resource_requirements": ("portal",),
        "auth_scope_requirements": ("hubspot:*",),
        "provider_constraints": {"limit_max": 100},
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "read",
        "execution_adapter": "hubspot.deals.search",
        "observation_adapter": "hubspot_deals_search_observation",
    },
    "quickbooks.invoices.list": {
        "capabilities": ("finance.invoices.read",),
        "required_parameters": (),
        "optional_parameters": ("limit", "start_position", "connector_id"),
        "parameter_source_rules": (
            _rule("realm_id", "RESOURCE_RESOLVER", "CONNECTOR_METADATA", aliases=("realmId", "company_id")),
            _rule("limit", "USER_EXPLICIT", "ACTION_DEFAULT", "MODEL_INFERENCE", aliases=("max_results",), default=25),
            _rule("start_position", "USER_EXPLICIT", "ACTION_DEFAULT", "MODEL_INFERENCE", aliases=("startPosition",), default=1),
        ),
        "resource_requirements": ("company",),
        "auth_scope_requirements": ("quickbooks:invoices:read", "quickbooks:*"),
        "provider_constraints": {"limit_max": 1000},
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "read",
        "execution_adapter": "quickbooks.invoices.list",
        "observation_adapter": "quickbooks_invoices_list_observation",
    },
    "zendesk.tickets.list": {
        "capabilities": ("support.tickets.read",),
        "required_parameters": (),
        "optional_parameters": ("status", "limit", "connector_id"),
        "parameter_source_rules": (
            _rule("subdomain", "RESOURCE_RESOLVER", "CONNECTOR_METADATA"),
            _rule("status", "USER_EXPLICIT", "TASK_CONTEXT", "MODEL_INFERENCE"),
            _rule("limit", "USER_EXPLICIT", "ACTION_DEFAULT", "MODEL_INFERENCE", default=25),
        ),
        "resource_requirements": ("subdomain",),
        "auth_scope_requirements": ("zendesk:tickets:read", "zendesk:*"),
        "provider_constraints": {"limit_max": 100},
        "availability_requirements": ("connector_connected", "auth_valid"),
        "governance_classification": "read",
        "execution_adapter": "zendesk.tickets.list",
        "observation_adapter": "zendesk_tickets_list_observation",
    },
}


def _empty(value: Any) -> bool:
    return value in (None, "", (), {}, [])


def compute_spec_revision(spec: ActionSpec) -> str:
    payload = {
        "id": spec.id,
        "kind": spec.kind,
        "required": list(spec.required_parameters),
        "optional": list(spec.optional_parameters),
        "resources": list(spec.resource_requirements),
        "constraints": spec.provider_constraints or {},
        "availability": list(spec.availability_requirements),
        "governance": spec.governance_classification,
        "rules": [
            {
                "parameter": rule.parameter,
                "sources": list(rule.sources),
                "required_by_api": rule.required_by_api,
                "required_from_user": rule.required_from_user,
            }
            for rule in spec.parameter_source_rules
        ],
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def materialize_action_spec(spec: ActionSpec) -> ActionSpec:
    """Fill empty F1 fields from the build overlay; catalog-owned fields win."""
    overlay = _OVERLAYS.get(spec.id)
    merged = spec
    if overlay:
        updates: dict[str, Any] = {}
        for key, value in overlay.items():
            if _empty(getattr(spec, key, None)):
                updates[key] = value
        if updates:
            merged = replace(spec, **updates)
    return replace(merged, spec_revision=compute_spec_revision(merged))


def _materialize_tuple(actions: tuple[ActionSpec, ...]) -> tuple[ActionSpec, ...]:
    return tuple(materialize_action_spec(action) for action in actions)


def materialize_vendor_catalog(catalog: dict[str, VendorCatalogSpec]) -> dict[str, VendorCatalogSpec]:
    """Apply F1 build-time augmentation once when the vendor catalog is constructed."""
    out: dict[str, VendorCatalogSpec] = {}
    for vendor, spec in catalog.items():
        out[vendor] = replace(
            spec,
            v1=_materialize_tuple(spec.v1),
            v2=_materialize_tuple(spec.v2),
            v3=_materialize_tuple(spec.v3),
            v4=_materialize_tuple(spec.v4),
        )
    return out


@lru_cache(maxsize=64)
def f1_overlay_keys() -> frozenset[str]:
    keys: set[str] = set(F1_CATALOG_ACTIONS)
    for catalog_key in F1_CATALOG_ACTIONS:
        keys.add(registry_action_key(catalog_key))
    return frozenset(keys)
