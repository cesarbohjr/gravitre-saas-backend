"""Phase 5: AI-proposed work lives in ``work_objects`` as status ``proposed``.

A proposal is not work yet. It carries its evidence and where it came from,
stays out of normal work lists, and becomes work only when a person accepts it
(``planned``) or goes away when they dismiss it (``archived``). Nothing runs
from a proposal by itself.

Duplicate proposals for the same thing are folded by ``dedupe_key``, which is
stored as ``external_entity_type='proposal'`` / ``external_entity_id`` so the
table's existing unique index enforces it.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

PROPOSAL_ENTITY_TYPE = "proposal"
MAX_EVIDENCE = 5


class ProposalError(ValueError):
    pass


def proposals_enabled(settings: Any) -> bool:
    return getattr(settings, "work_object_proposals_enabled", False) is True


def _now() -> str:
    return datetime.now(UTC).isoformat()


def propose_work_object(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    title: str,
    dedupe_key: str,
    source: str,
    evidence: list[dict[str, Any]],
    objective: str | None = None,
    department: str = "operations",
    object_type: str = "other",
    priority: str = "medium",
    goal_id: str | None = None,
    business_entity_id: str | None = None,
) -> dict[str, Any]:
    """File one proposal, or return the existing one for the same key."""
    if not proposals_enabled(settings):
        return {"skipped": "disabled"}
    title = (title or "").strip()[:200]
    if not title or not dedupe_key:
        raise ProposalError("title and dedupe_key are required")
    if not evidence:
        raise ProposalError("a proposal needs evidence")
    existing = (
        client.table("work_objects")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("external_entity_type", PROPOSAL_ENTITY_TYPE)
        .eq("external_entity_id", dedupe_key)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        return {"id": existing[0]["id"], "status": existing[0]["status"], "deduplicated": True}
    now = _now()
    row: dict[str, Any] = {
        "org_id": org_id,
        "object_type": object_type,
        "department": department,
        "title": title,
        "objective": (objective or "")[:800] or None,
        "status": "proposed",
        "priority": priority,
        "external_entity_type": PROPOSAL_ENTITY_TYPE,
        "external_entity_id": dedupe_key,
        "metadata": {
            "proposal": {
                "source": source,
                "evidence": evidence[:MAX_EVIDENCE],
                "proposed_at": now,
            }
        },
        "created_at": now,
        "updated_at": now,
        "last_activity_at": now,
    }
    if goal_id:
        row["goal_id"] = goal_id
    if business_entity_id:
        row["business_entity_id"] = business_entity_id
    res = client.table("work_objects").insert(row).execute()
    inserted = (res.data or [row])[0]
    return {"id": inserted.get("id"), "status": "proposed", "deduplicated": False}


def decide_proposal(
    client: Any,
    *,
    org_id: str,
    work_object_id: str,
    actor_id: str,
    accept: bool,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Accept (to ``planned``) or dismiss (to ``archived``) a pending proposal."""
    rows = (
        client.table("work_objects")
        .select("id, status, metadata")
        .eq("org_id", org_id)
        .eq("id", work_object_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    row = rows[0]
    if row.get("status") != "proposed":
        raise ProposalError(f"work object is {row.get('status')}, not a pending proposal")
    metadata = safe_normalize_stored_dict(row.get("metadata"))
    proposal = safe_normalize_stored_dict(metadata, key="proposal")
    proposal["decision"] = {
        "accepted": accept,
        "by": actor_id,
        "at": _now(),
        "reason": (reason or "")[:500] or None,
    }
    metadata["proposal"] = proposal
    new_status = "planned" if accept else "archived"
    (
        client.table("work_objects")
        .update({"status": new_status, "metadata": metadata, "updated_at": _now(), "last_activity_at": _now()})
        .eq("org_id", org_id)
        .eq("id", work_object_id)
        .eq("status", "proposed")  # a concurrent decision wins once
        .execute()
    )
    return {"id": work_object_id, "status": new_status}
