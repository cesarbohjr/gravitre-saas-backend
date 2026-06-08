"""Federated connector consent — time-boxed read-only tool access across B2B orgs (STA-117)."""
from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.agent_tool_permissions import ACTION_REQUIRED_SCOPES
from app.services.b2b_handoff_service import B2BHandoffError, get_active_partnership
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_GRANT_PROPOSED = "federation.grant.proposed"
AUDIT_GRANT_ACCEPTED = "federation.grant.accepted"
AUDIT_GRANT_REJECTED = "federation.grant.rejected"
AUDIT_GRANT_REVOKED = "federation.grant.revoked"
AUDIT_GRANT_EXPIRED = "federation.grant.expired"
AUDIT_FEDERATED_TOOL = "federation.tool.invoke"

GRANT_PENDING = "pending_grantee"
GRANT_ACTIVE = "active"
DEFAULT_EXPIRES_HOURS = 24
MAX_EXPIRES_HOURS = 168

WRITE_ACTION_MARKERS = (
    ".create",
    ".update",
    ".delete",
    ".write",
    ".enroll",
    ".post_message",
    ".send",
    ".post",
    ".acknowledge",
    ".resolve",
    ".reassign",
    ".comment",
    ".transition",
    ".assign",
    ".create",
)


class FederatedConnectorError(B2BHandoffError):
    code = "FEDERATED_CONNECTOR_ERROR"


@dataclass(frozen=True)
class FederatedToolContext:
    grant_id: str
    grantor_org_id: str
    grantee_org_id: str
    connector_id: str
    allowed_actions: tuple[str, ...]


def hash_federation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_read_only_action(action: str) -> bool:
    normalized = (action or "").strip().lower()
    if not normalized:
        return False
    if any(marker in normalized for marker in WRITE_ACTION_MARKERS):
        return False
    if normalized.endswith((".list", ".get", ".search")):
        return True
    scopes = ACTION_REQUIRED_SCOPES.get(normalized, [])
    return any(":read" in scope for scope in scopes)


def _serialize_grant(row: dict[str, Any], *, viewer_org_id: str, include_token: str | None = None) -> dict[str, Any]:
    partner_org_id = (
        str(row["grantee_org_id"]) if viewer_org_id == str(row["grantor_org_id"]) else str(row["grantor_org_id"])
    )
    payload = {
        "id": str(row["id"]),
        "partnershipId": str(row["partnership_id"]),
        "grantorOrgId": str(row["grantor_org_id"]),
        "granteeOrgId": str(row["grantee_org_id"]),
        "partnerOrgId": partner_org_id,
        "connectorId": str(row["connector_id"]),
        "label": row.get("label"),
        "allowedActions": list(row.get("allowed_actions") or []),
        "status": row["status"],
        "expiresAt": row.get("expires_at"),
        "createdAt": row.get("created_at"),
        "acceptedAt": row.get("accepted_at"),
        "revokedAt": row.get("revoked_at"),
    }
    if include_token:
        payload["accessToken"] = include_token
    return payload


def _get_grant(client: Any, grant_id: str) -> dict[str, Any] | None:
    result = (
        client.table("federated_connector_grants")
        .select("*")
        .eq("id", grant_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def _assert_grant_party(grant: dict[str, Any], org_id: str) -> None:
    if org_id not in {str(grant["grantor_org_id"]), str(grant["grantee_org_id"])}:
        raise FederatedConnectorError("Organization is not party to this grant", code="FORBIDDEN")


def _expire_if_needed(client: Any, grant: dict[str, Any]) -> dict[str, Any]:
    if grant.get("status") != GRANT_ACTIVE:
        return grant
    expires_at = grant.get("expires_at")
    if not expires_at:
        return grant
    try:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return grant
    if expiry > datetime.now(timezone.utc):
        return grant
    client.table("federated_connector_grants").update({"status": "expired"}).eq("id", grant["id"]).execute()
    write_audit_event(
        client,
        org_id=str(grant["grantor_org_id"]),
        actor_id=str(grant.get("accepted_by") or grant.get("proposed_by") or grant["grantor_org_id"]),
        action=AUDIT_GRANT_EXPIRED,
        resource_type="federated_connector_grant",
        resource_id=str(grant["id"]),
        metadata={"granteeOrgId": str(grant["grantee_org_id"])},
    )
    return {**grant, "status": "expired"}


def _validate_connector(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("id, org_id, type, status, name, vendor")
        .eq("id", connector_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
    )
    if not row:
        raise FederatedConnectorError("Connector not found in grantor organization", code="NOT_FOUND")
    connector = dict(row[0])
    if (connector.get("status") or "active") not in {"active", "connected", "healthy"}:
        raise FederatedConnectorError("Connector is not active", code="VALIDATION_ERROR")
    return connector


def propose_federated_grant(
    client: Any,
    *,
    grantor_org_id: str,
    grantee_org_id: str,
    connector_id: str,
    allowed_actions: list[str],
    actor_id: str,
    label: str | None = None,
    expires_in_hours: int = DEFAULT_EXPIRES_HOURS,
) -> dict[str, Any]:
    if grantor_org_id == grantee_org_id:
        raise FederatedConnectorError("Grantee must be a partner organization", code="VALIDATION_ERROR")
    if not allowed_actions:
        raise FederatedConnectorError("At least one allowed action is required", code="VALIDATION_ERROR")
    invalid = [action for action in allowed_actions if not is_read_only_action(action)]
    if invalid:
        raise FederatedConnectorError(
            f"Only read-only actions are allowed for federated grants: {', '.join(invalid)}",
            code="VALIDATION_ERROR",
        )
    hours = max(1, min(int(expires_in_hours), MAX_EXPIRES_HOURS))
    partnership = get_active_partnership(client, grantor_org_id, grantee_org_id)
    if not partnership:
        raise FederatedConnectorError(
            "Active B2B partnership required before sharing connector access",
            code="PARTNERSHIP_REQUIRED",
        )
    _validate_connector(client, grantor_org_id, connector_id)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    row = {
        "partnership_id": str(partnership["id"]),
        "grantor_org_id": grantor_org_id,
        "grantee_org_id": grantee_org_id,
        "connector_id": connector_id,
        "label": label,
        "allowed_actions": allowed_actions,
        "status": GRANT_PENDING,
        "expires_at": expires_at,
        "proposed_by": actor_id,
    }
    result = client.table("federated_connector_grants").insert(row).execute()
    if not result.data:
        raise RuntimeError("federated_connector_grants insert returned no row")
    grant = dict(result.data[0])
    write_audit_event(
        client,
        org_id=grantor_org_id,
        actor_id=actor_id,
        action=AUDIT_GRANT_PROPOSED,
        resource_type="federated_connector_grant",
        resource_id=str(grant["id"]),
        metadata={
            "granteeOrgId": grantee_org_id,
            "connectorId": connector_id,
            "allowedActions": allowed_actions,
            "expiresAt": expires_at,
        },
    )
    return _serialize_grant(grant, viewer_org_id=grantor_org_id)


def list_federated_grants(client: Any, org_id: str) -> list[dict[str, Any]]:
    grantor = (
        client.table("federated_connector_grants")
        .select("*")
        .eq("grantor_org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    grantee = (
        client.table("federated_connector_grants")
        .select("*")
        .eq("grantee_org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = {str(row["id"]): _expire_if_needed(client, dict(row)) for row in (grantor.data or []) + (grantee.data or [])}
    return [_serialize_grant(row, viewer_org_id=org_id) for row in rows.values()]


def get_federated_grant(client: Any, org_id: str, grant_id: str) -> dict[str, Any]:
    grant = _get_grant(client, grant_id)
    if not grant:
        raise FederatedConnectorError("Grant not found", code="NOT_FOUND")
    _assert_grant_party(grant, org_id)
    grant = _expire_if_needed(client, grant)
    return _serialize_grant(grant, viewer_org_id=org_id)


def accept_federated_grant(
    client: Any,
    *,
    org_id: str,
    grant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    grant = _get_grant(client, grant_id)
    if not grant:
        raise FederatedConnectorError("Grant not found", code="NOT_FOUND")
    if str(grant["grantee_org_id"]) != org_id:
        raise FederatedConnectorError("Only the grantee organization can accept this grant", code="FORBIDDEN")
    if grant["status"] != GRANT_PENDING:
        raise FederatedConnectorError(f"Grant is not pending (status={grant['status']})", code="CONFLICT")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("federated_connector_grants")
        .update(
            {
                "status": GRANT_ACTIVE,
                "access_token_hash": hash_federation_token(token),
                "accepted_by": actor_id,
                "accepted_at": now,
            }
        )
        .eq("id", grant_id)
        .execute()
    )
    row = dict((updated.data or [grant])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_GRANT_ACCEPTED,
        resource_type="federated_connector_grant",
        resource_id=grant_id,
        metadata={"grantorOrgId": str(grant["grantor_org_id"]), "connectorId": str(grant["connector_id"])},
    )
    return _serialize_grant(row, viewer_org_id=org_id, include_token=token)


def reject_federated_grant(
    client: Any,
    *,
    org_id: str,
    grant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    grant = _get_grant(client, grant_id)
    if not grant:
        raise FederatedConnectorError("Grant not found", code="NOT_FOUND")
    if str(grant["grantee_org_id"]) != org_id:
        raise FederatedConnectorError("Only the grantee organization can reject this grant", code="FORBIDDEN")
    if grant["status"] != GRANT_PENDING:
        raise FederatedConnectorError(f"Grant is not pending (status={grant['status']})", code="CONFLICT")

    updated = (
        client.table("federated_connector_grants")
        .update({"status": "rejected"})
        .eq("id", grant_id)
        .execute()
    )
    row = dict((updated.data or [grant])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_GRANT_REJECTED,
        resource_type="federated_connector_grant",
        resource_id=grant_id,
        metadata={},
    )
    return _serialize_grant(row, viewer_org_id=org_id)


def revoke_federated_grant(
    client: Any,
    *,
    org_id: str,
    grant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    grant = _get_grant(client, grant_id)
    if not grant:
        raise FederatedConnectorError("Grant not found", code="NOT_FOUND")
    _assert_grant_party(grant, org_id)
    if grant["status"] not in {GRANT_PENDING, GRANT_ACTIVE}:
        raise FederatedConnectorError(f"Grant cannot be revoked (status={grant['status']})", code="CONFLICT")

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("federated_connector_grants")
        .update({"status": "revoked", "revoked_by": actor_id, "revoked_at": now, "access_token_hash": None})
        .eq("id", grant_id)
        .execute()
    )
    row = dict((updated.data or [grant])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_GRANT_REVOKED,
        resource_type="federated_connector_grant",
        resource_id=grant_id,
        metadata={},
    )
    return _serialize_grant(row, viewer_org_id=org_id)


def resolve_federated_tool_context(
    client: Any,
    *,
    grantee_org_id: str,
    action: str,
    federation_token: str | None = None,
    federation_grant_id: str | None = None,
) -> FederatedToolContext:
    grant: dict[str, Any] | None = None
    if federation_token:
        token_hash = hash_federation_token(federation_token.strip())
        result = (
            client.table("federated_connector_grants")
            .select("*")
            .eq("access_token_hash", token_hash)
            .limit(1)
            .execute()
        )
        if result.data:
            grant = dict(result.data[0])
    elif federation_grant_id:
        grant = _get_grant(client, federation_grant_id)

    if not grant:
        raise FederatedConnectorError("Federated grant not found", code="NOT_FOUND")
    grant = _expire_if_needed(client, grant)
    if str(grant["grantee_org_id"]) != grantee_org_id:
        raise FederatedConnectorError("Federated grant is not issued to this organization", code="FORBIDDEN")
    if grant["status"] != GRANT_ACTIVE:
        raise FederatedConnectorError(f"Federated grant is not active (status={grant['status']})", code="FORBIDDEN")

    allowed = [str(item) for item in (grant.get("allowed_actions") or [])]
    if action not in allowed:
        raise FederatedConnectorError(f"Action {action} is not allowed by this federated grant", code="FORBIDDEN")

    return FederatedToolContext(
        grant_id=str(grant["id"]),
        grantor_org_id=str(grant["grantor_org_id"]),
        grantee_org_id=str(grant["grantee_org_id"]),
        connector_id=str(grant["connector_id"]),
        allowed_actions=tuple(allowed),
    )


def audit_federated_tool_invoke(
    client: Any,
    *,
    grant: FederatedToolContext,
    action: str,
    actor_id: str,
    success: bool,
) -> None:
    write_audit_event(
        client,
        org_id=grant.grantee_org_id,
        actor_id=actor_id,
        action=AUDIT_FEDERATED_TOOL,
        resource_type="federated_connector_grant",
        resource_id=grant.grant_id,
        metadata={
            "grantorOrgId": grant.grantor_org_id,
            "connectorId": grant.connector_id,
            "toolAction": action,
            "success": success,
        },
    )
