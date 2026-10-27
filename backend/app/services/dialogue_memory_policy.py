"""Server-side opt-in for canonical dialogue memory; no new memory store."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from types import SimpleNamespace

from app.core.safe_dict import safe_normalize_stored_dict


@dataclass(frozen=True)
class DialogueMemoryAccess:
    recall: bool = False
    learn: bool = False
    retention_days: int | None = None
    reason: str = "not_authorized"


def load_dialogue_memory_access(client: Any, org_id: str, user_id: str | None) -> DialogueMemoryAccess:
    """No cache: revocation and membership removal apply on the next read/write.

    Policy lives in organizations.settings.dialogueMemory, writable through the
    existing capability-protected settings API. No policy, malformed values, missing actor,
    or failed reads mean no durable memory access, including for service jobs.
    """
    if client is None or not org_id or not user_id:
        return DialogueMemoryAccess(reason="missing_identity")
    try:
        members = client.table("organization_members").select("org_id,user_id").eq("org_id", org_id).eq("user_id", user_id).limit(1).execute().data or []
        if not any(isinstance(r, dict) and r.get("org_id") == org_id and r.get("user_id") == user_id for r in members):
            return DialogueMemoryAccess(reason="not_member")
        orgs = client.table("organizations").select("id,settings").eq("id", org_id).limit(1).execute().data or []
        row = next((r for r in orgs if isinstance(r, dict) and r.get("id") == org_id), {})
        policy = safe_normalize_stored_dict(safe_normalize_stored_dict(row, key="settings"), key="dialogueMemory")
        allowed = policy.get("actorIds")
        if allowed is not None and (not isinstance(allowed, list) or any(not isinstance(v, str) for v in allowed) or user_id not in allowed):
            return DialogueMemoryAccess(reason="actor_denied")
        days = policy.get("retentionDays")
        if days is not None and (type(days) is not int or not 1 <= days <= 3650):
            return DialogueMemoryAccess(reason="invalid_policy")
        return DialogueMemoryAccess(
            recall=policy.get("recallEnabled") is True,
            learn=policy.get("learnEnabled") is True,
            retention_days=days,
            reason="policy_loaded",
        )
    except Exception:
        return DialogueMemoryAccess(reason="policy_unavailable")


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def live_memory_row(row: dict, *, org_id: str, user_id: str | None, now: datetime, retention_days: int | None = None) -> bool:
    if row.get("org_id") != org_id or row.get("deleted_at") or row.get("superseded_by"):
        return False
    if row.get("is_active") is not True or row.get("is_current") is not True:
        return False
    visibility = row.get("visibility", "org")
    if visibility == "private":
        if not user_id or row.get("created_by") != user_id:
            return False
    elif visibility not in ("org", "workspace", "department", "agent"):
        return False
    for field in ("expires_at", "valid_until"):
        if row.get(field) is not None:
            deadline = _date(row[field])
            if deadline is None or deadline <= now:
                return False
    if row.get("valid_from") is not None:
        start = _date(row["valid_from"])
        if start is None or start > now:
            return False
    if retention_days is not None:
        created = _date(row.get("created_at"))
        if created is None or created <= now - timedelta(days=retention_days):
            return False
    return True


def filter_dialogue_recall(client: Any, org_id: str, user_id: str | None, rows: list[dict], *, retention_days: int | None = None, agent_id: str | None = None, diagnostics: dict | None = None) -> list[dict]:
    """Rehydrate authoritative records so stale search hits cannot revive deletes.

    Metadata-less graph/ledger hits are excluded in governed mode. Existing
    recall/liveness services still choose candidates; this is the final gate.
    """
    ids = sorted({str(r["id"]) for r in rows if isinstance(r, dict) and r.get("id")})
    if diagnostics is not None:
        diagnostics.update({"candidates": len(rows), "permitted": 0, "reason": "no_verified_rows"})
    if not ids or client is None:
        return []
    try:
        found = client.table("agent_memories").select("*").eq("org_id", org_id).in_("id", ids).execute().data or []
    except Exception:
        if diagnostics is not None:
            diagnostics["reason"] = "metadata_unavailable"
        return []
    now = datetime.now(timezone.utc)
    current = {str(r.get("id")): r for r in found if isinstance(r, dict) and live_memory_row(r, org_id=org_id, user_id=user_id, now=now, retention_days=retention_days)}
    from app.services.memory_source_liveness import drop_memories_from_revoked_sources

    # Governed recall always honors connector revocation, even if the legacy
    # rollout flag is off. The existing helper fails closed on lookup errors.
    live = drop_memories_from_revoked_sources(
        client, org_id, list(current.values()),
        settings=SimpleNamespace(memory_source_lineage_enabled=True),
        surface="governed_dialogue_recall",
    )
    current = {str(r["id"]): r for r in live}
    kept = []
    seen = set()
    for hit in rows:
        rid = str(hit.get("id") or "")
        row = current.get(rid)
        if row is None or rid in seen:
            continue
        # Department rows have already passed the department-scoped service.
        # Workspace/agent recalls must not import another agent's private data.
        if row.get("agent_id") and row.get("agent_id") != agent_id:
            continue
        seen.add(rid)
        kept.append({**hit, **row})
    if diagnostics is not None:
        diagnostics.update({"permitted": len(kept), "reason": "filtered"})
    return kept
