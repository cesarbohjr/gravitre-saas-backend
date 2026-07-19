"""CF soft-rank service — STA-314 suggest-only reorder after heuristics.

Cold start: returns payload unchanged when volume gate fails.
Never executes tools; never drops cards.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.ml.cf_interaction_ingest import (
    LOOKBACK_DAYS,
    item_affinity_scores,
    load_scored_interactions,
    training_gate_status,
)
from app.ml.cf_soft_rank import soft_rank_cards

logger = get_logger(__name__)

_FORBIDDEN = (
    "execute_plan",
    "invoke_tool",
    "toolName",
    "approvalId",
    "arguments",
)


def soft_rank_heuristic_payload(
    client: Any,
    org_id: str,
    payload: dict[str, Any],
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Apply CF soft-rank when gate ready; otherwise cold-start (heuristics order)."""
    gate = training_gate_status(client, org_id, lookback_days=lookback_days)
    out = dict(payload)
    out["advisoryOnly"] = True
    out["cfGate"] = gate
    out["cfRanked"] = False

    cards = list(payload.get("recommendations") or [])
    if not cards:
        out["recommendations"] = []
        out["count"] = 0
        return out

    if not gate.get("ready"):
        # Cold start — keep heuristic order; annotate for clients.
        annotated = []
        for card in cards:
            row = dict(card)
            row.setdefault("cf_ranked", False)
            annotated.append(row)
        out["recommendations"] = annotated
        out["count"] = len(annotated)
        return out

    try:
        interactions = load_scored_interactions(client, org_id, lookback_days=lookback_days)
        affinity = item_affinity_scores(interactions)
        ranked = soft_rank_cards(cards, affinity)
        # Never drop: append any missing ids (defensive).
        ranked_ids = {str(c.get("id") or "") for c in ranked}
        for card in cards:
            cid = str(card.get("id") or "")
            if cid and cid not in ranked_ids:
                ranked.append(dict(card))
        out["recommendations"] = ranked
        out["count"] = len(ranked)
        out["cfRanked"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("cf_soft_rank_failed org_id=%s err=%s", org_id, exc)
        out["recommendations"] = cards
        out["count"] = len(cards)
        out["cfRanked"] = False
        out["cfError"] = exc.__class__.__name__

    _assert_no_execute(out)
    return out


def _assert_no_execute(payload: dict[str, Any]) -> None:
    stack: list[Any] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _FORBIDDEN:
                    raise AssertionError(f"forbidden CF payload key: {key}")
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
