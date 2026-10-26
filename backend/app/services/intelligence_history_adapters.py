"""Connector transport adapters for historical Intelligence Overview backfills.

Real provider HTTP clients are injected by the connector runtime after the
usual OAuth/scope checks. This boundary can be tested entirely offline.
"""
from __future__ import annotations
from typing import Any, Callable

from app.services.intelligence_history_pipeline import ALLOWED_TYPES

PROVIDER_OBJECTS: dict[str, frozenset[str]] = {
    "hubspot": frozenset({"contact", "company", "deal"}),
    "zendesk": frozenset({"contact", "ticket"}),
    "salesforce": frozenset({"contact", "company", "deal"}),
    "stripe": frozenset({"invoice"}),
}
# The connector runtime must verify scopes through the provider's grant ledger.
# These are capability identifiers; they are not OAuth authorization claims.
READ_CAPABILITIES = {
    "contact": "contacts.read",
    "company": "companies.read",
    "ticket": "tickets.read",
    "deal": "deals.read",
    "invoice": "invoices.read",
}


class HistoricalProviderAdapter:
    def __init__(
        self, provider: str,
        read_page: Callable[[str, dict[str, Any], int], dict[str, Any]],
    ):
        if provider not in PROVIDER_OBJECTS:
            raise ValueError("Unsupported historical provider")
        self.provider = provider
        self._read_page = read_page

    def fetch_page(self, object_type: str, cursor: dict[str, Any], limit: int) -> dict[str, Any]:
        if object_type not in ALLOWED_TYPES or object_type not in PROVIDER_OBJECTS[self.provider]:
            raise ValueError("Provider object type not supported")
        page = self._read_page(object_type, cursor, limit)
        if not isinstance(page, dict):
            raise ValueError("Malformed provider page")
        source_rows = page.get("records")
        if not isinstance(source_rows, list):
            raise ValueError("Provider records missing")
        records = []
        for row in source_rows:
            if not isinstance(row, dict):
                raise ValueError("Malformed source record")
            # Common CRM payloads expose identifiers nested under properties.
            properties = row.get("properties")
            if not isinstance(properties, dict):
                properties = {}
            external_id = row.get("id") or row.get("external_id")
            if external_id is None:
                raise ValueError("Provider object has no immutable ID")
            email = row.get("email") or properties.get("email")
            domain = row.get("domain") or properties.get("domain")
            normalized = dict(row)
            normalized["id"] = str(external_id)
            if email is not None:
                normalized["email"] = email
            if domain is not None:
                normalized["domain"] = domain
            records.append(normalized)
        return {"records": records, "next_cursor": page.get("next_cursor")}


def authorized_history_object(connector: dict[str, Any], object_type: str) -> bool:
    """Fail closed when user consent, capability grants or scope proof is missing.

    This is an additional gate, not a replacement for runtime token scope
    checking or RBAC. The caller must authorize connector ownership first.
    """
    provider = str(connector.get("type") or "").lower()
    if provider not in PROVIDER_OBJECTS or object_type not in PROVIDER_OBJECTS[provider]:
        return False
    config = connector.get("config") or {}
    if not isinstance(config, dict) or config.get("history_sync_enabled") is not True:
        return False
    grants = connector.get("verified_read_capabilities")
    if not isinstance(grants, list):
        return False
    return READ_CAPABILITIES[object_type] in grants
