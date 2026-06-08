"""Cross-org B2B agent handoff protocol (STA-116).

Extends the intra-org handoff bus (STA-17) with mutual org partnership consent
and per-handoff receiver acceptance before briefings cross tenant boundaries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.handoff_service import build_handoff_briefing, get_agent
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_PARTNERSHIP_INVITED = "federation.partnership.invited"
AUDIT_PARTNERSHIP_ACCEPTED = "federation.partnership.accepted"
AUDIT_PARTNERSHIP_REJECTED = "federation.partnership.rejected"
AUDIT_PARTNERSHIP_REVOKED = "federation.partnership.revoked"
AUDIT_HANDOFF_SENT = "federation.handoff.sent"
AUDIT_HANDOFF_ACCEPTED = "federation.handoff.accepted"
AUDIT_HANDOFF_REJECTED = "federation.handoff.rejected"
AUDIT_HANDOFF_COMPLETED = "federation.handoff.completed"

PARTNERSHIP_ACTIVE = "active"
PARTNERSHIP_PENDING = "pending_partner"
HANDOFF_PENDING = "pending_receiver"
HANDOFF_ACCEPTED = "accepted"


class B2BHandoffError(Exception):
    code = "B2B_HANDOFF_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def normalize_org_pair(org_id: str, partner_org_id: str) -> tuple[str, str]:
    if org_id == partner_org_id:
        raise B2BHandoffError("Cannot create a partnership with the same organization", code="VALIDATION_ERROR")
    return (org_id, partner_org_id) if org_id < partner_org_id else (partner_org_id, org_id)


def _partner_org_id(partnership: dict[str, Any], viewer_org_id: str) -> str:
    org_a = str(partnership["org_a_id"])
    org_b = str(partnership["org_b_id"])
    if viewer_org_id == org_a:
        return org_b
    if viewer_org_id == org_b:
        return org_a
    raise B2BHandoffError("Organization is not a member of this partnership", code="FORBIDDEN")


def _serialize_partnership(row: dict[str, Any], viewer_org_id: str) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "orgAId": str(row["org_a_id"]),
        "orgBId": str(row["org_b_id"]),
        "partnerOrgId": _partner_org_id(row, viewer_org_id),
        "invitedByOrgId": str(row["invited_by_org_id"]),
        "status": row["status"],
        "initiatorConsentAt": row.get("initiator_consent_at"),
        "partnerConsentAt": row.get("partner_consent_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def _serialize_handoff(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "partnershipId": str(row["partnership_id"]),
        "senderOrgId": str(row["sender_org_id"]),
        "receiverOrgId": str(row["receiver_org_id"]),
        "fromAgentId": str(row["from_agent_id"]) if row.get("from_agent_id") else None,
        "toAgentId": str(row["to_agent_id"]) if row.get("to_agent_id") else None,
        "briefing": row.get("briefing") or {},
        "message": row.get("message"),
        "status": row["status"],
        "createdAt": row.get("created_at"),
        "acceptedAt": row.get("accepted_at"),
        "completedAt": row.get("completed_at"),
    }


def _get_partnership(client: Any, partnership_id: str) -> dict[str, Any] | None:
    result = (
        client.table("org_b2b_partnerships")
        .select("*")
        .eq("id", partnership_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def _assert_org_in_partnership(partnership: dict[str, Any], org_id: str) -> None:
    if org_id not in {str(partnership["org_a_id"]), str(partnership["org_b_id"])}:
        raise B2BHandoffError("Organization is not a member of this partnership", code="FORBIDDEN")


def _assert_org_exists(client: Any, org_id: str) -> None:
    row = client.table("organizations").select("id").eq("id", org_id).limit(1).execute().data
    if not row:
        raise B2BHandoffError("Partner organization not found", code="NOT_FOUND")


def invite_partner_org(
    client: Any,
    *,
    org_id: str,
    partner_org_id: str,
    actor_id: str,
) -> dict[str, Any]:
    _assert_org_exists(client, partner_org_id)
    org_a_id, org_b_id = normalize_org_pair(org_id, partner_org_id)
    existing = (
        client.table("org_b2b_partnerships")
        .select("*")
        .eq("org_a_id", org_a_id)
        .eq("org_b_id", org_b_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        partnership = dict(existing.data[0])
        if partnership["status"] == PARTNERSHIP_ACTIVE:
            return _serialize_partnership(partnership, org_id)
        if partnership["status"] == PARTNERSHIP_PENDING:
            return _serialize_partnership(partnership, org_id)
        raise B2BHandoffError(
            f"Partnership is {partnership['status']}; revoke or contact support before re-inviting",
            code="CONFLICT",
        )

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "org_a_id": org_a_id,
        "org_b_id": org_b_id,
        "invited_by_org_id": org_id,
        "status": PARTNERSHIP_PENDING,
        "initiator_consent_at": now,
        "invited_by": actor_id,
    }
    result = client.table("org_b2b_partnerships").insert(row).execute()
    if not result.data:
        raise RuntimeError("org_b2b_partnerships insert returned no row")
    partnership = dict(result.data[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PARTNERSHIP_INVITED,
        resource_type="org_b2b_partnership",
        resource_id=str(partnership["id"]),
        metadata={"partnerOrgId": partner_org_id},
    )
    logger.info("b2b_partnership_invited org_id=%s partner_org_id=%s", org_id, partner_org_id)
    return _serialize_partnership(partnership, org_id)


def list_partnerships(client: Any, org_id: str) -> list[dict[str, Any]]:
    result_a = (
        client.table("org_b2b_partnerships")
        .select("*")
        .eq("org_a_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    result_b = (
        client.table("org_b2b_partnerships")
        .select("*")
        .eq("org_b_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = {str(row["id"]): dict(row) for row in (result_a.data or []) + (result_b.data or [])}
    return [_serialize_partnership(row, org_id) for row in rows.values()]


def accept_partnership(
    client: Any,
    *,
    org_id: str,
    partnership_id: str,
    actor_id: str,
) -> dict[str, Any]:
    partnership = _get_partnership(client, partnership_id)
    if not partnership:
        raise B2BHandoffError("Partnership not found", code="NOT_FOUND")
    _assert_org_in_partnership(partnership, org_id)
    if str(partnership["invited_by_org_id"]) == org_id:
        raise B2BHandoffError("Inviting organization cannot accept its own invite", code="VALIDATION_ERROR")
    if partnership["status"] != PARTNERSHIP_PENDING:
        raise B2BHandoffError(f"Partnership is not pending (status={partnership['status']})", code="CONFLICT")

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("org_b2b_partnerships")
        .update({"status": PARTNERSHIP_ACTIVE, "partner_consent_at": now})
        .eq("id", partnership_id)
        .execute()
    )
    row = dict((updated.data or [partnership])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PARTNERSHIP_ACCEPTED,
        resource_type="org_b2b_partnership",
        resource_id=partnership_id,
        metadata={"invitedByOrgId": str(partnership["invited_by_org_id"])},
    )
    return _serialize_partnership(row, org_id)


def reject_partnership(
    client: Any,
    *,
    org_id: str,
    partnership_id: str,
    actor_id: str,
) -> dict[str, Any]:
    partnership = _get_partnership(client, partnership_id)
    if not partnership:
        raise B2BHandoffError("Partnership not found", code="NOT_FOUND")
    _assert_org_in_partnership(partnership, org_id)
    if partnership["status"] != PARTNERSHIP_PENDING:
        raise B2BHandoffError(f"Partnership is not pending (status={partnership['status']})", code="CONFLICT")

    updated = (
        client.table("org_b2b_partnerships")
        .update({"status": "rejected"})
        .eq("id", partnership_id)
        .execute()
    )
    row = dict((updated.data or [partnership])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PARTNERSHIP_REJECTED,
        resource_type="org_b2b_partnership",
        resource_id=partnership_id,
        metadata={},
    )
    return _serialize_partnership(row, org_id)


def revoke_partnership(
    client: Any,
    *,
    org_id: str,
    partnership_id: str,
    actor_id: str,
) -> dict[str, Any]:
    partnership = _get_partnership(client, partnership_id)
    if not partnership:
        raise B2BHandoffError("Partnership not found", code="NOT_FOUND")
    _assert_org_in_partnership(partnership, org_id)
    if partnership["status"] not in {PARTNERSHIP_ACTIVE, PARTNERSHIP_PENDING}:
        raise B2BHandoffError(f"Partnership cannot be revoked (status={partnership['status']})", code="CONFLICT")

    updated = (
        client.table("org_b2b_partnerships")
        .update({"status": "revoked"})
        .eq("id", partnership_id)
        .execute()
    )
    row = dict((updated.data or [partnership])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_PARTNERSHIP_REVOKED,
        resource_type="org_b2b_partnership",
        resource_id=partnership_id,
        metadata={},
    )
    return _serialize_partnership(row, org_id)


def get_active_partnership(client: Any, org_id: str, partner_org_id: str) -> dict[str, Any] | None:
    org_a_id, org_b_id = normalize_org_pair(org_id, partner_org_id)
    result = (
        client.table("org_b2b_partnerships")
        .select("*")
        .eq("org_a_id", org_a_id)
        .eq("org_b_id", org_b_id)
        .eq("status", PARTNERSHIP_ACTIVE)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def create_cross_org_handoff(
    client: Any,
    *,
    sender_org_id: str,
    receiver_org_id: str,
    from_agent_id: str | None,
    to_agent_id: str | None,
    briefing: dict[str, Any] | None,
    parameters: dict[str, Any] | None,
    source_output: dict[str, Any] | None,
    message: str | None,
    sender_user_id: str,
) -> dict[str, Any]:
    partnership = get_active_partnership(client, sender_org_id, receiver_org_id)
    if not partnership:
        raise B2BHandoffError(
            "Active B2B partnership required before sending cross-org handoffs",
            code="PARTNERSHIP_REQUIRED",
        )

    if from_agent_id:
        agent = get_agent(client, sender_org_id, from_agent_id)
        if not agent:
            raise B2BHandoffError("Sender agent not found in your organization", code="NOT_FOUND")
    if to_agent_id:
        agent = get_agent(client, receiver_org_id, to_agent_id)
        if not agent:
            raise B2BHandoffError("Receiver agent not found in partner organization", code="NOT_FOUND")

    payload = briefing or build_handoff_briefing(
        parameters=parameters or {},
        source_output=source_output,
    )
    row = {
        "partnership_id": str(partnership["id"]),
        "sender_org_id": sender_org_id,
        "receiver_org_id": receiver_org_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "briefing": payload,
        "message": message,
        "status": HANDOFF_PENDING,
        "sender_user_id": sender_user_id,
    }
    result = client.table("cross_org_handoffs").insert(row).execute()
    if not result.data:
        raise RuntimeError("cross_org_handoffs insert returned no row")
    handoff = dict(result.data[0])
    write_audit_event(
        client,
        org_id=sender_org_id,
        actor_id=sender_user_id,
        action=AUDIT_HANDOFF_SENT,
        resource_type="cross_org_handoff",
        resource_id=str(handoff["id"]),
        metadata={
            "receiverOrgId": receiver_org_id,
            "toAgentId": to_agent_id,
            "fromAgentId": from_agent_id,
        },
    )
    return _serialize_handoff(handoff)


def list_cross_org_handoffs(
    client: Any,
    org_id: str,
    *,
    direction: str = "all",
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if direction in {"all", "outbound"}:
        query = (
            client.table("cross_org_handoffs")
            .select("*")
            .eq("sender_org_id", org_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        rows.extend(dict(row) for row in (query.execute().data or []))
    if direction in {"all", "inbound"}:
        query = (
            client.table("cross_org_handoffs")
            .select("*")
            .eq("receiver_org_id", org_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        rows.extend(dict(row) for row in (query.execute().data or []))
    deduped = {str(row["id"]): row for row in rows}
    return [_serialize_handoff(row) for row in deduped.values()]


def get_cross_org_handoff(client: Any, org_id: str, handoff_id: str) -> dict[str, Any]:
    result = (
        client.table("cross_org_handoffs")
        .select("*")
        .eq("id", handoff_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    row = dict(result.data[0])
    if org_id not in {str(row["sender_org_id"]), str(row["receiver_org_id"])}:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    return _serialize_handoff(row)


def accept_cross_org_handoff(
    client: Any,
    *,
    org_id: str,
    handoff_id: str,
    actor_id: str,
) -> dict[str, Any]:
    result = (
        client.table("cross_org_handoffs")
        .select("*")
        .eq("id", handoff_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    handoff = dict(result.data[0])
    if str(handoff["receiver_org_id"]) != org_id:
        raise B2BHandoffError("Only the receiver organization can accept this handoff", code="FORBIDDEN")
    if handoff["status"] != HANDOFF_PENDING:
        raise B2BHandoffError(f"Handoff is not pending (status={handoff['status']})", code="CONFLICT")

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("cross_org_handoffs")
        .update(
            {
                "status": HANDOFF_ACCEPTED,
                "receiver_user_id": actor_id,
                "accepted_at": now,
            }
        )
        .eq("id", handoff_id)
        .execute()
    )
    row = dict((updated.data or [handoff])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_HANDOFF_ACCEPTED,
        resource_type="cross_org_handoff",
        resource_id=handoff_id,
        metadata={"senderOrgId": str(handoff["sender_org_id"])},
    )
    return _serialize_handoff(row)


def reject_cross_org_handoff(
    client: Any,
    *,
    org_id: str,
    handoff_id: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    result = (
        client.table("cross_org_handoffs")
        .select("*")
        .eq("id", handoff_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    handoff = dict(result.data[0])
    if str(handoff["receiver_org_id"]) != org_id:
        raise B2BHandoffError("Only the receiver organization can reject this handoff", code="FORBIDDEN")
    if handoff["status"] != HANDOFF_PENDING:
        raise B2BHandoffError(f"Handoff is not pending (status={handoff['status']})", code="CONFLICT")

    updated = (
        client.table("cross_org_handoffs")
        .update({"status": "rejected", "error_message": reason, "receiver_user_id": actor_id})
        .eq("id", handoff_id)
        .execute()
    )
    row = dict((updated.data or [handoff])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_HANDOFF_REJECTED,
        resource_type="cross_org_handoff",
        resource_id=handoff_id,
        metadata={"reason": reason},
    )
    return _serialize_handoff(row)


def complete_cross_org_handoff(
    client: Any,
    *,
    org_id: str,
    handoff_id: str,
    actor_id: str,
) -> dict[str, Any]:
    result = (
        client.table("cross_org_handoffs")
        .select("*")
        .eq("id", handoff_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    handoff = dict(result.data[0])
    if org_id not in {str(handoff["sender_org_id"]), str(handoff["receiver_org_id"])}:
        raise B2BHandoffError("Handoff not found", code="NOT_FOUND")
    if handoff["status"] != HANDOFF_ACCEPTED:
        raise B2BHandoffError("Handoff must be accepted before completion", code="CONFLICT")

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("cross_org_handoffs")
        .update({"status": "completed", "completed_at": now})
        .eq("id", handoff_id)
        .execute()
    )
    row = dict((updated.data or [handoff])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_HANDOFF_COMPLETED,
        resource_type="cross_org_handoff",
        resource_id=handoff_id,
        metadata={},
    )
    return _serialize_handoff(row)
