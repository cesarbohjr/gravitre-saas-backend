"""Workspace-scoped cross-conversation memory (Part 1 item 1).

Persists typed memories into ``agent_memories`` (org-scoped; ``agent_id`` nullable).
RECALL uses category filter + hybrid content match + existing ledger path (kernel).
No Option C fuzzy person matching.

Memory hardening (2026-09): temporal supersede, structured extraction, contamination
defense, and deterministic lifecycle — all via shared helpers, not call-site patches.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.memory_contamination_guard import (
    LINEAGE_COLUMNS,
    SOURCE_UNTRUSTED_EXTERNAL,
    attach_recall_honesty,
    lineage_required,
    memory_source_lineage,
    validate_memory_write,
)
from app.services.memory_extraction_service import extract_typed_memories_structured
from app.services.memory_source_liveness import drop_memories_from_revoked_sources
from app.services.memory_temporal_service import (
    APPEND_ONLY_CATEGORIES,
    TEMPORAL_CATEGORIES,
    normalize_memory_key,
    upsert_temporal_memory,
)

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

# Provenance for turn-promoted memories when the caller gives none. Contains no
# user marker, so the contamination guard classifies it as model inference.
DEFAULT_TURN_PROVENANCE = "model_extracted_turn"

_HARDENING_COLUMNS = frozenset(
    {
        "memory_key",
        "valid_from",
        "valid_until",
        "superseded_by",
        "is_current",
        "source_class",
        "structured_payload",
    }
)


def _insert_memory_row(client: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Insert with hardened columns; fall back to legacy shape if migration pending."""
    try:
        inserted = client.table("agent_memories").insert(payload).execute().data or []
        if inserted and isinstance(inserted[0], dict):
            return inserted[0]
        return payload
    except Exception as first_exc:  # noqa: BLE001
        if any(k in payload for k in LINEAGE_COLUMNS):
            # Lineage is emitted only after its flag is enabled. Never silently
            # create an unrevocable memory when its required schema/write fails.
            logger.warning("workspace_memory_lineage_write_refused error=%s", type(first_exc).__name__)
            return None
        legacy = {
            k: v for k, v in payload.items() if k not in _HARDENING_COLUMNS and k not in LINEAGE_COLUMNS
        }
        try:
            inserted = client.table("agent_memories").insert(legacy).execute().data or []
            if inserted and isinstance(inserted[0], dict):
                logger.debug("workspace_memory_insert_legacy_fallback reason=%s", first_exc)
                return inserted[0]
            return legacy
        except Exception as exc:  # noqa: BLE001
            logger.debug("workspace_memory_insert_failed error=%s", exc)
            return None


def _retract_if_superseded(client: Any, org_id: str, row: dict[str, Any]) -> bool:
    """Deactivate a row whose turn was cancelled while the insert was in flight.

    The last check runs before the insert; a cancel landing during the round
    trip would otherwise leave a durable memory from a cancelled turn.
    """
    from app.services.turn_cancellation import superseded_write

    if not superseded_write("memory.promote_turn_memories.commit"):
        return False
    row_id = row.get("id")
    if row_id:
        try:
            client.table("agent_memories").update({"is_active": False}).eq("id", row_id).eq(
                "org_id", org_id
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("workspace_memory_retract_failed id=%s error=%s", row_id, exc)
    return True


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
    Temporal categories supersede on ``memory_key``; append-only categories insert.
    Returns inserted row dicts (best-effort).
    """
    active_settings = settings or get_settings()
    if not client or not org_id or not memories:
        return []
    from app.services.speculative_execution import defer_if_speculative

    if defer_if_speculative(
        "memory.promote_turn_memories",
        promote_turn_memories,
        client,
        org_id=org_id,
        memories=memories,
        agent_id=agent_id,
        conversation_id=conversation_id,
        user_id=user_id,
        settings=settings,
        provenance=provenance,
    ):
        # Unconfirmed speech never writes memory; replayed only if adopted.
        return []
    from app.services.turn_cancellation import superseded_write

    if superseded_write("memory.promote_turn_memories"):
        # The turn these memories came from was cancelled or corrected.
        return []

    written: list[dict[str, Any]] = []
    # Default provenance is model-extracted: memories promoted from a turn are the
    # model's reading of it, not a user statement. Callers that know the user said
    # it pass an explicit user provenance (e.g. "user_statement").
    base_prov = (provenance or DEFAULT_TURN_PROVENANCE).strip() or DEFAULT_TURN_PROVENANCE
    if conversation_id:
        base_prov = f"{base_prov}:conversation:{conversation_id}"

    # No agent given → workspace scope (agent_id NULL, nullable since
    # 20260813170000). Never borrow an arbitrary agent as a "steward".
    resolved_agent_id = (str(agent_id).strip() or None) if agent_id else None

    for raw in memories:
        if not isinstance(raw, dict):
            continue
        enriched = validate_memory_write(raw, provenance=base_prov)
        content = str(enriched.get("content") or enriched.get("memory_text") or "").strip()
        if not content:
            continue
        category = str(enriched.get("category") or "episodic").strip().lower()
        if category not in _WRITE_CATEGORIES:
            category = "episodic"
        try:
            confidence = float(
                enriched.get("confidence") if enriched.get("confidence") is not None else 80
            )
        except (TypeError, ValueError):
            confidence = 80.0
        confidence = max(0.0, min(100.0, confidence))

        memory_key = enriched.get("memory_key") or normalize_memory_key(
            category,
            content,
            enriched.get("explicit_key"),
        )

        payload: dict[str, Any] = {
            "id": str(enriched.get("id") or uuid4()),
            "org_id": org_id,
            "agent_id": resolved_agent_id,
            "content": content[:4000],
            "category": category,
            "provenance": str(enriched.get("provenance") or base_prov)[:500],
            "confidence": confidence,
            "editable": True,
            "created_by": user_id,
            "is_active": True,
            "source_class": enriched.get("source_class"),
            "structured_payload": enriched.get("structured_payload"),
            "is_current": True,
        }
        if memory_key:
            payload["memory_key"] = memory_key
        # Connector lineage (source_connector_id / source_record_ref) when the
        # candidate names the connection it came from and the flag is on.
        lineage = memory_source_lineage(enriched, settings=active_settings)
        if (
            not lineage
            and enriched.get("source_class") == SOURCE_UNTRUSTED_EXTERNAL
            and lineage_required(active_settings)
        ):
            # Connector or document content that cannot name its connection could
            # never be removed when that connection goes: do not store it.
            logger.info("workspace_memory_skipped_no_lineage org_id=%s category=%s", org_id, category)
            continue
        payload.update(lineage)

        try:
            from app.rag.embedding import get_embedding

            emb = get_embedding(content, active_settings, org_id=org_id)
            if emb:
                payload["embedding"] = emb
        except Exception as exc:  # noqa: BLE001
            logger.debug("workspace_memory_embed_skipped error=%s", exc)

        if superseded_write("memory.promote_turn_memories"):
            # Checked again right before each write: the lookup and embedding
            # above take long enough for the turn to be cancelled meanwhile.
            # (Not between a temporal upsert's insert and its supersede update,
            # which must land together.)
            break
        try:
            if category in TEMPORAL_CATEGORIES and memory_key:
                row = upsert_temporal_memory(
                    client,
                    payload,
                    change_reason=enriched.get("change_reason"),
                )
                if row:
                    written.append(row)
            else:
                inserted = _insert_memory_row(client, payload)
                if inserted and _retract_if_superseded(client, org_id, inserted):
                    break
                if inserted:
                    written.append(inserted)
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
    include_history: bool = False,
    memory_key: str | None = None,
) -> list[dict[str, Any]]:
    """Recall org-scoped memories by category + hybrid content match.

    Always filters ``org_id``. Current temporal rows only (``is_current=true``).
    Includes workspace rows (``agent_id`` null) and same-org agent rows.
    Does not perform Option C fuzzy person match.
    """
    _ = settings
    if not client or not org_id:
        return []

    if memory_key and include_history:
        from app.services.memory_temporal_service import get_memory_history

        history = get_memory_history(client, org_id, memory_key)
        history = drop_memories_from_revoked_sources(
            client, org_id, history, settings=settings, surface="workspace_memory_history"
        )
        return [attach_recall_honesty(h) for h in history]

    limit = max(1, min(int(top_k), 50))
    cats = [c.strip().lower() for c in (categories or []) if c and str(c).strip()]
    cats = [c for c in cats if c in _WRITE_CATEGORIES]

    select_cols = (
        "id,org_id,agent_id,category,content,confidence,provenance,"
        "usage_count,created_at,is_active,memory_key,source_class,"
        "structured_payload,is_current,valid_from,valid_until"
    )

    try:
        q = (
            client.table("agent_memories")
            .select(select_cols)
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(max(limit * 4, 40))
        )
        try:
            q = q.eq("is_active", True)
        except Exception:  # noqa: BLE001
            pass
        try:
            q = q.eq("is_current", True)
        except Exception:  # noqa: BLE001
            pass
        if memory_key:
            q = q.eq("memory_key", memory_key)
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
        if row.get("is_current") is False:
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
        labeled = attach_recall_honesty(
            {
                **row,
                "score": round(score, 4),
                "source": "workspace_memory_recall",
            }
        )
        scored.append((score, labeled))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    ranked = [item for _, item in scored]
    # Never recall a memory learned from a connector that is no longer live, even
    # before the disconnect purge has run (no-op unless lineage is on).
    ranked = drop_memories_from_revoked_sources(
        client, org_id, ranked, settings=settings, surface="workspace_memory_recall"
    )
    return ranked[:limit]


def extract_typed_memories_from_act(
    act_result: dict[str, Any] | None,
    *,
    outcome_event: str | None = None,
    message: str | None = None,
) -> list[dict[str, Any]]:
    """Pull structured typed memories from act_result; no raw transcript replay."""
    return extract_typed_memories_structured(
        act_result,
        outcome_event=outcome_event,
        message=message,
    )


__all__ = [
    "APPEND_ONLY_CATEGORIES",
    "TEMPORAL_CATEGORIES",
    "TYPED_CATEGORIES",
    "extract_typed_memories_from_act",
    "promote_turn_memories",
    "recall_workspace",
]
