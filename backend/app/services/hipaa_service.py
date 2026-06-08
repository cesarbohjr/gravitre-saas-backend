"""HIPAA BAA workflow and PHI handling controls (STA-110)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.data_residency_service import get_org_data_region
from app.workflows.audit import write_audit_event

CURRENT_BAA_VERSION = "2026.1"
REQUIRED_HIPAA_DATA_REGION = "us"

# External-facing tools blocked unless HIPAA mode is active (BAA + enabled + US region).
PHI_SENSITIVE_ACTIONS = frozenset(
    {
        "email.send",
        "webhook.post",
        "slack.post_message",
    }
)

AUDIT_BAA_ACCEPTED = "enterprise.hipaa.baa_accepted"
AUDIT_HIPAA_ENABLED = "enterprise.hipaa.enabled"
AUDIT_HIPAA_DISABLED = "enterprise.hipaa.disabled"
AUDIT_PHI_CONNECTOR_TAGGED = "connector.phi_capable.updated"


class HipaaComplianceError(Exception):
    code = "HIPAA_REQUIRED"

    def __init__(self, message: str = "HIPAA mode with accepted BAA is required for this action") -> None:
        super().__init__(message)


def _org_row(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings,data_region").eq("id", org_id).limit(1).execute().data
    if not row:
        raise ValueError("Organization not found")
    return row[0]


def _hipaa_settings(org_settings: dict[str, Any]) -> dict[str, Any]:
    enterprise = org_settings.get("enterprise") if isinstance(org_settings.get("enterprise"), dict) else {}
    hipaa = enterprise.get("hipaa") if isinstance(enterprise.get("hipaa"), dict) else {}
    return dict(hipaa)


def get_hipaa_status(client: Any, org_id: str) -> dict[str, Any]:
    org = _org_row(client, org_id)
    org_settings = org.get("settings") if isinstance(org.get("settings"), dict) else {}
    hipaa = _hipaa_settings(org_settings)
    data_region = get_org_data_region(org_settings, data_region=org.get("data_region"))
    baa_accepted = bool(hipaa.get("baaAcceptedAt"))
    enabled = bool(hipaa.get("enabled"))
    phi_connectors = (
        client.table("connectors")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("phi_capable", True)
        .execute()
    )
    phi_count = int(getattr(phi_connectors, "count", None) or len(phi_connectors.data or []))
    hipaa_ready = enabled and baa_accepted and data_region == REQUIRED_HIPAA_DATA_REGION
    return {
        "enabled": enabled,
        "baaAccepted": baa_accepted,
        "baaVersion": hipaa.get("baaVersion"),
        "baaAcceptedAt": hipaa.get("baaAcceptedAt"),
        "baaAcceptedBy": hipaa.get("baaAcceptedBy"),
        "requiredBaaVersion": CURRENT_BAA_VERSION,
        "dataRegion": data_region,
        "hipaaReady": hipaa_ready,
        "phiCapableConnectorCount": phi_count,
        "blockedActionsWhenInactive": sorted(PHI_SENSITIVE_ACTIONS),
    }


def is_hipaa_ready(client: Any, org_id: str) -> bool:
    return bool(get_hipaa_status(client, org_id)["hipaaReady"])


def accept_baa(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    baa_version: str | None = None,
) -> dict[str, Any]:
    version = (baa_version or CURRENT_BAA_VERSION).strip()
    if version != CURRENT_BAA_VERSION:
        raise ValueError(f"BAA version must be {CURRENT_BAA_VERSION}")

    org = _org_row(client, org_id)
    org_settings = dict(org.get("settings") or {})
    enterprise = dict(org_settings.get("enterprise") or {})
    hipaa = dict(_hipaa_settings(org_settings))
    now = datetime.now(timezone.utc).isoformat()
    hipaa.update(
        {
            "baaVersion": version,
            "baaAcceptedAt": now,
            "baaAcceptedBy": actor_id,
        }
    )
    enterprise["hipaa"] = hipaa
    org_settings["enterprise"] = enterprise
    client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
    client.table("org_hipaa_baa_acceptances").insert(
        {
            "org_id": org_id,
            "accepted_by": actor_id,
            "baa_version": version,
            "accepted_at": now,
        }
    ).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_BAA_ACCEPTED,
        resource_type="organization",
        resource_id=org_id,
        metadata={"baaVersion": version},
    )
    return get_hipaa_status(client, org_id)


def set_hipaa_enabled(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    enabled: bool,
) -> dict[str, Any]:
    org = _org_row(client, org_id)
    org_settings = dict(org.get("settings") or {})
    enterprise = dict(org_settings.get("enterprise") or {})
    hipaa = dict(_hipaa_settings(org_settings))
    data_region = get_org_data_region(org_settings, data_region=org.get("data_region"))

    if enabled:
        if not hipaa.get("baaAcceptedAt"):
            raise ValueError("Accept the Business Associate Agreement before enabling HIPAA mode")
        if data_region != REQUIRED_HIPAA_DATA_REGION:
            raise ValueError("HIPAA mode requires US data residency")

    hipaa["enabled"] = enabled
    enterprise["hipaa"] = hipaa
    org_settings["enterprise"] = enterprise
    client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_HIPAA_ENABLED if enabled else AUDIT_HIPAA_DISABLED,
        resource_type="organization",
        resource_id=org_id,
        metadata={"enabled": enabled, "dataRegion": data_region},
    )
    return get_hipaa_status(client, org_id)


def set_connector_phi_capable(
    client: Any,
    *,
    org_id: str,
    connector_id: str,
    phi_capable: bool,
    actor_id: str,
) -> dict[str, Any]:
    updated = (
        client.table("connectors")
        .update({"phi_capable": phi_capable})
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .execute()
    )
    if not updated.data:
        raise ValueError("Connector not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PHI_CONNECTOR_TAGGED,
        resource_type="connector",
        resource_id=connector_id,
        metadata={"phiCapable": phi_capable},
    )
    return dict(updated.data[0])


def connector_handles_phi(connector: dict[str, Any] | None) -> bool:
    if not connector:
        return False
    return bool(connector.get("phi_capable"))


def enforce_hipaa_for_tool_invoke(
    client: Any,
    org_id: str,
    action: str,
    connector_id: str | None,
) -> None:
    if is_hipaa_ready(client, org_id):
        return

    if action in PHI_SENSITIVE_ACTIONS:
        raise HipaaComplianceError(
            f"Tool action {action} is blocked until HIPAA mode is enabled with an accepted BAA"
        )

    if not connector_id:
        return

    row = (
        client.table("connectors")
        .select("id, phi_capable")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
        .data
    )
    if row and connector_handles_phi(row[0]):
        raise HipaaComplianceError(
            "PHI-capable connectors cannot be used until HIPAA mode is enabled with an accepted BAA"
        )
