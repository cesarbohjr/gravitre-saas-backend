"""White-label inheritance for MSP client workspaces.

A client workspace with no white label of its own shows its MSP's branding.
Resolved at read time; nothing is copied, so the MSP's later changes apply and
the client can still set its own branding (which then wins).
Only the look is inherited: custom domains and their verification stay per org.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.branding_service import DEFAULT_BRANDING, get_org_branding

logger = get_logger(__name__)

INHERITABLE_KEYS = ("logoUrl", "primaryColor", "hidePoweredBy", "emailFromName")


def has_own_branding(org_settings: dict[str, Any] | None) -> bool:
    enterprise = (org_settings or {}).get("enterprise")
    branding = enterprise.get("branding") if isinstance(enterprise, dict) else None
    if not isinstance(branding, dict):
        return False
    for key in INHERITABLE_KEYS:
        value = branding.get(key)
        if value not in (None, "", DEFAULT_BRANDING.get(key)):
            return True
    return False


def inherited_branding(client: Any, org_id: str, org_settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """MSP branding values for ``org_id`` when it should inherit, else None.

    Requires a live, active msp_clients relationship that matches the parent
    link; a stale parent_org_id alone never pulls another org's branding.
    """
    if has_own_branding(org_settings):
        return None
    try:
        rows = (
            client.table("msp_clients")
            .select("msp_org_id,status")
            .eq("client_org_id", org_id)
            .eq("status", "active")
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows or not isinstance(rows[0], dict):
            return None
        msp_org_id = str(rows[0].get("msp_org_id") or "")
        if not msp_org_id:
            return None
        msp_rows = (
            client.table("organizations").select("id,name,settings").eq("id", msp_org_id).limit(1).execute().data
            or []
        )
        if not msp_rows or str(msp_rows[0].get("id")) != msp_org_id:
            return None
        msp_settings = msp_rows[0].get("settings") if isinstance(msp_rows[0].get("settings"), dict) else {}
        if not has_own_branding(msp_settings):
            return None
        msp_branding = get_org_branding(msp_settings)
        return {
            "values": {key: msp_branding.get(key) for key in INHERITABLE_KEYS},
            "from": {"id": msp_org_id, "name": msp_rows[0].get("name") or "Your partner"},
        }
    except Exception as exc:  # noqa: BLE001 - table missing before migration, or transient read error
        logger.info("msp_branding_inherit_skipped org_id=%s error=%s", org_id, type(exc).__name__)
        return None


def apply_inherited_branding(client: Any, org_id: str, org_settings: dict[str, Any] | None, branding: dict[str, Any]) -> dict[str, Any]:
    """Return ``branding`` with the MSP's look filled in when inheriting."""
    inherited = inherited_branding(client, org_id, org_settings)
    if not inherited:
        return branding
    merged = dict(branding)
    merged.update(inherited["values"])
    merged["inheritedFrom"] = inherited["from"]
    return merged
