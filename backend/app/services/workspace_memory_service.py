"""Workspace-scoped cross-conversation memory (Part 1 item 1).

Persists typed memories into ``agent_memories`` (org-scoped; ``agent_id`` nullable).
RECALL uses category filter + hybrid content match + existing ledger path (kernel).
No Option C fuzzy person matching.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TYPED_CATEGORIES = frozenset(
    {
        "decision",
        "outcome",
        "relationship",
        "procedural",
        "preference",
        "episodic",
    }
)

# Accept legacy + cognitive taxonomy on write; typed set is preferred for promote.
_WRITE_CATEGORIES = TYPED_CATEGORIES | frozenset(
    {"fact", "pattern", "rule", "working", "campaign_learning", "risk_signal", "business_rule"}
)


def promote_turn_memories(
    client: Any,
    *,
    org_id: str,
    memories: list[dict[str, Any]] | None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
    settings: Settings | None = None,
    provenance: str | None = None,
) -> list[dict[str, Any]]:
    """Persist typed memories from a confirmed turn into ``agent_memories``.

    Rows are org-scoped. ``agent_id`` may be None (workspace scope). Never raises.
    Returns inserted row dicts (best-effort).
    """
    _ = settings or get_settings()
    if not client or not org_id or not memories:
        return []

    written: list[dict[str, Any]] = []
    base_prov = (provenance or "confirmed_turn").strip() or "confirmed_turn"
    if conversation_id:
        base_prov = f"{base_prov}:conversation:{conversation_id}"

    # Until agent_id is nullable in prod, pin workspace rows to an org steward agent
    # while keeping org-wide RECALL (workspace-scoped product semantics).
    resolved_agent_id = (str(agent_id).strip() or None) if agent_id else None
    if not resolved_agent_id:
        try:
            rows = (
                client.table("agents")
                .select("id")
                .eq("org_id", org_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                resolved_agent_id = str(rows[0].get("id") or "") or None
                base_prov = f"{base_prov}:workspace_steward"
        except Exception as exc:  # noqa: BLE001
            logger.debug("workspace_memory_steward_lookup_failed error=%s", exc)

    for raw in memories:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or raw.get("memory_text") or "").strip()
        if not content:
            continue
        category = str(raw.get("category") or "episodic").strip().lower()
        if category not in _WRITE_CATEGORIES:
            category = "episodic"
        try:
            confidence = float(raw.get("confidence") if raw.get("confidence") is not None else 80)
        except (TypeError, ValueError):
            confidence = 80.0
        confidence = max(0.0, min(100.0, confidence))

        payload: dict[str, Any] = {
            "id": str(raw.get("id") or uuid4()),
            "org_id": org_id,
            "agent_id": resolved_agent_id,
            "content": content[:4000],
            "category": category,
            "provenance": str(raw.get("provenance") or base_prov)[:500],
            "confidence": confidence,
            "editable": True,
            "created_by": user_id,
            "is_active": True,
        }
        if not resolved_agent_id:
            # Cannot insert without agent_id until migration applied — skip honestly.
            logger.warning(
                "workspace_memory_promote_skipped_no_steward org_id=%s",
                org_id,
            )
            continue
        # Optional embedding — best-effort; recall still works via content/category.
        try:
            from app.rag.embedding import get_embedding

            active = settings or get_settings()
            emb = get_embedding(content, active, org_id=org_id)
            if emb:
                payload["embedding"] = emb
        except Exception as exc:  # noqa: BLE001
            logger.debug("workspace_memory_embed_skipped error=%s", exc)

        try:
            inserted = client.table("agent_memories").insert(payload).execute().data or []
            if inserted and isinstance(inserted[0], dict):
                written.append(inserted[0])
            else:
                written.append(payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("workspace_memory_promote_failed error=%s", exc)

    if written:
        logger.info(
            "workspace_memory_promoted org_id=%s count=%s conversation_id=%s",
            org_id,
            len(written),
            conversation_id,
        )
    return written


def recall_workspace(
    client: Any,
    *,
    org_id: str,
    query: str = "",
    categories: list[str] | None = None,
    top_k: int = 12,
    agent_id: str | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Recall org-scoped memories by category + hybrid content match.

    Always filters ``org_id``. Includes workspace rows (``agent_id`` null) and
    same-org agent rows. Does not perform Option C fuzzy person match.
    """
    _ = settings
    if not client or not org_id:
        return []

    limit = max(1, min(int(top_k), 50))
    cats = [c.strip().lower() for c in (categories or []) if c and str(c).strip()]
    cats = [c for c in cats if c in _WRITE_CATEGORIES]

    try:
        q = (
            client.table("agent_memories")
            .select(
                "id,org_id,agent_id,category,content,confidence,provenance,"
                "usage_count,created_at,is_active"
            )
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(max(limit * 4, 40))
        )
        # Prefer active rows when column present (PostgREST ignores unknown filters
        # only if column missing — we already migrated is_active).
        try:
            q = q.eq("is_active", True)
        except Exception:  # noqa: BLE001
            pass
        if len(cats) == 1:
            q = q.eq("category", cats[0])
        rows = q.execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("workspace_memory_recall_query_failed error=%s", exc)
        return []

    needle = (query or "").strip().lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("org_id") or "") != org_id:
            continue
        if cats and str(row.get("category") or "").lower() not in cats:
            continue
        content = str(row.get("content") or "")
        content_l = content.lower()
        score = 0.35  # confidence-honesty-ok: internal relevance rank, not user-facing confidence
        if needle:
            if needle in content_l:
                score = 0.92  # confidence-honesty-ok
            elif any(tok and tok in content_l for tok in needle.split() if len(tok) > 2):
                score = 0.62  # confidence-honesty-ok
            else:
                score = 0.25  # confidence-honesty-ok
        # Slight preference for workspace (null agent) and matching agent.
        row_agent = row.get("agent_id")
        if row_agent is None:
            score += 0.05
        elif agent_id and str(row_agent) == str(agent_id):
            score += 0.08
        try:
            conf = float(row.get("confidence") or 0)
            if conf <= 1.0:
                conf *= 100.0
            score += min(conf, 100.0) / 1000.0
        except (TypeError, ValueError):
            pass
        scored.append(
            (
                score,
                {
                    **row,
                    "score": round(score, 4),
                    "source": "workspace_memory_recall",
                },
            )
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def extract_typed_memories_from_act(
    act_result: dict[str, Any] | None,
    *,
    outcome_event: str | None = None,
    message: str | None = None,
) -> list[dict[str, Any]]:
    """Pull explicit typed memories from act_result; optional outcome stub."""
    out: list[dict[str, Any]] = []
    if isinstance(act_result, dict):
        for key in ("typed_memories", "memories", "workspace_memories"):
            raw = act_result.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and (item.get("content") or item.get("memory_text")):
                        out.append(item)
        # Single explicit fields
        content = act_result.get("memory_content") or act_result.get("decision")
        category = str(act_result.get("memory_category") or "").strip().lower()
        if content and category in TYPED_CATEGORIES:
            out.append({"content": str(content), "category": category})

    if outcome_event and message:
        out.append(
            {
                "content": f"Outcome ({outcome_event}): {(message or '')[:500]}",
                "category": "outcome",
                "confidence": 70,
                "provenance": f"learn_outcome:{outcome_event}",
            }
        )
    return out
