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


# Demo category templates for marketplace install (Phase 1).
CONNECTOR_CATEGORY_TEMPLATES: dict[str, dict[str, Any]] = {
    "executive-intelligence-sources": {
        "name": "Executive Intelligence Sources",
        "description": "Gravitree-managed public/aggregate sources (FRED, SEC, World Bank, OECD).",
        "connectors": ["fred", "sec_edgar", "world_bank", "oecd", "opencorporates"],
    },
    "msp-intelligence-sources": {
        "name": "MSP Intelligence Sources",
        "description": "Vulnerability and KEV feeds (Gravitree-managed).",
        "connectors": ["nvd", "cisa_kev"],
    },
    "sales-intelligence-sources": {
        "name": "Sales Intelligence Sources",
        "description": (
            "Customer CRM + discovery stubs (HubSpot, Apollo). "
            "Does not stage Crunchbase/PDL or BYO ZoomInfo/LI Sales Nav."
        ),
        "connectors": ["hubspot", "apollo"],
    },
    "prospecting-intelligence-sources": {
        "name": "Prospecting Intelligence Sources",
        "description": (
            "Outbound discovery stubs (Apollo + HubSpot for list sync). "
            "Does not stage Crunchbase/PDL (STA-312). BYO ZoomInfo/LI Sales Nav via separate template."
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
