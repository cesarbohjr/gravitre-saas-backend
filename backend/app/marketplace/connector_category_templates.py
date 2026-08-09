"""Marketplace template staging — create needs_connection connector stubs."""
from __future__ import annotations

from typing import Any

from app.connectors.repository import create_connector, list_connectors
from app.core.logging import get_logger
from app.intelligence_packs.shared.auth_mode import get_auth_mode

logger = get_logger(__name__)

NEEDS_CONNECTION = "needs_connection"


def _existing_types(client: Any, org_id: str, *, environment_name: str) -> dict[str, dict[str, Any]]:
    rows = list_connectors(client, org_id, environment_name=environment_name) or []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ctype = str(row.get("type") or "").strip().lower()
        if ctype and ctype not in out:
            out[ctype] = dict(row)
    return out


def stage_connector_stubs(
    client: Any,
    org_id: str,
    connector_types: list[str],
    *,
    created_by: str | None,
    environment_name: str = "production",
    template_id: str | None = None,
) -> dict[str, Any]:
    """Pre-stage connectors as needs_connection without authenticating.

    Idempotent: skips types that already have any non-deleted connector row.
    Does NOT create working/active connections.
    """
    existing = _existing_types(client, org_id, environment_name=environment_name)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for raw in connector_types:
        ctype = str(raw or "").strip().lower()
        if not ctype:
            continue
        if ctype in existing:
            row = existing[ctype]
            skipped.append(
                {
                    "connectorType": ctype,
                    "reason": "already_exists",
                    "status": row.get("status"),
                    "id": row.get("id"),
                }
            )
            continue
        auth_mode = get_auth_mode(ctype).value
        config = {
            "staged": True,
            "auth_mode": auth_mode,
            "template_id": template_id,
            "needs_connection": True,
        }
        row = create_connector(
            client,
            org_id,
            ctype,
            config,
            created_by,
            environment_name=environment_name,
            status=NEEDS_CONNECTION,
        )
        created.append(
            {
                "connectorType": ctype,
                "id": row.get("id"),
                "status": row.get("status"),
                "authMode": auth_mode,
            }
        )
        logger.info(
            "connector_stub_staged org_id=%s type=%s status=%s template=%s",
            org_id,
            ctype,
            NEEDS_CONNECTION,
            template_id,
        )

    return {
        "created": created,
        "skipped": skipped,
        "stagedCount": len(created),
        "templateId": template_id,
        "note": "Stubs are needs_connection only — no credentials applied",
    }


# Acceptable statuses for tip stub coverage (staged awaiting auth OR already live).
_STAGED_OK_STATUSES = frozenset(
    {"needs_connection", "pending_auth", "pending", "active", "connected", "healthy"}
)
_ACTIVE_STATUSES = frozenset({"active", "connected", "healthy"})


def connector_stub_coverage(
    client: Any,
    org_id: str,
    connector_types: list[str],
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Per-type connector snapshot for pack tip evidence (no OAuth).

    Returns ids/statuses for each requested type. ``coverageOk`` is true when every
    type has a non-deleted row in a staged-or-active status.
    """
    existing = _existing_types(client, org_id, environment_name=environment_name)
    by_type: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for raw in connector_types:
        ctype = str(raw or "").strip().lower()
        if not ctype:
            continue
        row = existing.get(ctype)
        if not row:
            missing.append(ctype)
            by_type[ctype] = {"id": None, "status": None, "stagedOk": False, "active": False}
            continue
        status = str(row.get("status") or "").lower()
        by_type[ctype] = {
            "id": str(row["id"]) if row.get("id") else None,
            "status": status or None,
            "stagedOk": status in _STAGED_OK_STATUSES,
            "active": status in _ACTIVE_STATUSES,
        }
    covered = [t for t, info in by_type.items() if info.get("stagedOk")]
    return {
        "byType": by_type,
        "required": [str(t).strip().lower() for t in connector_types if str(t or "").strip()],
        "coveredCount": len(covered),
        "requiredCount": len(by_type),
        "missing": missing,
        "notStagedOk": [t for t, info in by_type.items() if not info.get("stagedOk")],
        "coverageOk": len(missing) == 0 and all(info.get("stagedOk") for info in by_type.values()),
    }


# Demo category templates for marketplace install (Phase 1).
CONNECTOR_CATEGORY_TEMPLATES: dict[str, dict[str, Any]] = {
    "executive-intelligence-sources": {
        "name": "Executive Intelligence Sources",
        "description": "Gravitre-managed public/aggregate sources (FRED, SEC, World Bank, OECD).",
        "connectors": ["fred", "sec_edgar", "world_bank", "oecd", "opencorporates"],
    },
    "msp-intelligence-sources": {
        "name": "MSP Intelligence Sources",
        "description": (
            "MSP prospecting stubs (Apollo + HubSpot) plus Gravitre-managed "
            "vulnerability feeds (NVD, CISA KEV)."
        ),
        "connectors": ["apollo", "hubspot", "nvd", "cisa_kev"],
    },
    "sales-intelligence-sources": {
        "name": "Sales Intelligence Sources",
        "description": (
            "Customer CRM + discovery stubs (HubSpot, Apollo). "
            "PDL/SEMrush-style BYO and Crunchbase are not auto-staged — connect via Connectors."
        ),
        "connectors": ["hubspot", "apollo"],
    },
    "prospecting-intelligence-sources": {
        "name": "Prospecting Intelligence Sources",
        "description": (
            "Outbound discovery stubs (Apollo + HubSpot for list sync). "
            "PDL is BYO via Connectors (not auto-staged). Crunchbase stays activation-gated. "
            "BYO ZoomInfo/LI Sales Nav via separate template."
        ),
        "connectors": ["apollo", "hubspot"],
    },
    "customer-success-intelligence-sources": {
        "name": "Customer Success Intelligence Sources",
        "description": (
            "Internal CRM + support stubs (HubSpot, Zendesk). "
            "No new external enrichment vendors."
        ),
        "connectors": ["hubspot", "zendesk"],
    },
    "marketing-intelligence-sources": {
        "name": "Marketing Intelligence Sources",
        "description": (
            "GSC + GA4 + HubSpot stubs. SEMrush/Ahrefs/PDL are BYO via Connectors (not auto-staged)."
        ),
        "connectors": ["google_search_console", "google_analytics", "hubspot"],
    },
    "revops-intelligence-sources": {
        "name": "RevOps Intelligence Sources",
        "description": (
            "CRM rollup stubs (HubSpot; Salesforce optional). "
            "Finance pack F3 unlocked separately (finance-intelligence-sources)."
        ),
        "connectors": ["hubspot", "salesforce"],
    },
    "ai-search-intelligence-sources": {
        "name": "AI Search Intelligence Sources",
        "description": (
            "Finseo + AI Visibility UI stubs. Ahrefs is BYO via Connectors "
            "(reuse Marketing Ahrefs when already connected)."
        ),
        "connectors": ["finseo", "ai_visibility_ui", "ahrefs"],
    },
    "finance-intelligence-sources": {
        "name": "Finance Intelligence Sources",
        "description": (
            "F3 stubs: QuickBooks, Xero, NetSuite, Plaid (if entitled). "
            "Staged needs_connection only — no live secrets at install."
        ),
        "connectors": ["quickbooks", "xero", "netsuite", "plaid"],
    },
    "hr-talent-intelligence-sources": {
        "name": "HR & Talent Intelligence Sources",
        "description": (
            "H3 stubs: Workday, BambooHR, Greenhouse, Gusto. "
            "Gusto stays partner-OAuth gated until approved."
        ),
        "connectors": ["workday", "bamboohr", "greenhouse", "gusto"],
    },
    "byo-premium-prospecting": {
        "name": "BYO Premium Prospecting",
        "description": "Customer-subscription providers — fail closed without your own keys.",
        "connectors": ["zoominfo", "linkedin_sales_navigator"],
    },
}


def install_connector_category_template(
    client: Any,
    org_id: str,
    template_id: str,
    *,
    created_by: str | None,
    environment_name: str = "production",
) -> dict[str, Any]:
    spec = CONNECTOR_CATEGORY_TEMPLATES.get(template_id)
    if not spec:
        raise ValueError(f"Unknown connector category template: {template_id}")
    result = stage_connector_stubs(
        client,
        org_id,
        list(spec["connectors"]),
        created_by=created_by,
        environment_name=environment_name,
        template_id=template_id,
    )
    result["name"] = spec["name"]
    result["description"] = spec["description"]
    # Explicit acceptance criterion: install must not leave any new row as active/connected.
    for row in result["created"]:
        if str(row.get("status")) in {"active", "connected", "healthy"}:
            raise RuntimeError("Template install created a live connection — forbidden")
    return result
