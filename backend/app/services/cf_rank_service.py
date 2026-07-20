"""CF soft-rank service — STA-314 suggest-only reorder after heuristics.

Prefers trained matrix factorization when available; falls back to item affinity.
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
from app.ml.cf_soft_rank import card_item_keys, soft_rank_cards

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
    actor_id: str | None = None,
    settings: Any | None = None,
    factorizer: Any | None = None,
) -> dict[str, Any]:
    """Apply CF soft-rank when gate ready; otherwise cold-start (heuristics order)."""
    gate = training_gate_status(client, org_id, lookback_days=lookback_days)
    out = dict(payload)
    out["advisoryOnly"] = True
    out["cfGate"] = gate
    out["cfRanked"] = False
    out["cfMethod"] = "cold_start"

    cards = list(payload.get("recommendations") or [])
    if not cards:
        out["recommendations"] = []
        out["count"] = 0
        return out

    def _preserve_estimate(card: dict[str, Any], *, cf_ranked: bool, method: str) -> dict[str, Any]:
        # Module C: CF may reorder from outcome interactions, but card confidence
        # numbers remain heuristic estimates until a separate outcome scorer lands.
        row = dict(card)
        row.setdefault("cf_ranked", cf_ranked)
        row.setdefault("cf_method", method)
        row.setdefault("confidenceIsEstimate", True)
        row.setdefault("confidence_is_estimate", True)
        row.setdefault("confidenceSource", "heuristic")
        row.setdefault("confidence_source", "heuristic")
        return row

    if not gate.get("ready"):
        annotated = [_preserve_estimate(card, cf_ranked=False, method="cold_start") for card in cards]
        out["recommendations"] = annotated
        out["count"] = len(annotated)
        return out

    try:
        interactions = load_scored_interactions(client, org_id, lookback_days=lookback_days)
        affinity = item_affinity_scores(interactions)
        mf_scores, method = _mf_scores_for_cards(
            org_id,
            cards,
            actor_id=actor_id,
            settings=settings,
            factorizer=factorizer,
        )
        ranked = soft_rank_cards(
            cards,
            affinity,
            mf_scores=mf_scores,
            method=method,
        )
        ranked_ids = {str(c.get("id") or "") for c in ranked}
        for card in cards:
            cid = str(card.get("id") or "")
            if cid and cid not in ranked_ids:
                ranked.append(dict(card))
        out["recommendations"] = [
            _preserve_estimate(card, cf_ranked=True, method=method) for card in ranked
        ]
        out["count"] = len(out["recommendations"])
        out["cfRanked"] = True
        out["cfMethod"] = method
        out["rankingSource"] = "outcome_interactions" if method != "cold_start" else "cold_start"
    except Exception as exc:  # noqa: BLE001
        logger.warning("cf_soft_rank_failed org_id=%s err=%s", org_id, exc)
        out["recommendations"] = cards
        out["count"] = len(cards)
        out["cfRanked"] = False
        out["cfMethod"] = "error"
        out["cfError"] = exc.__class__.__name__

    _assert_no_execute(out)
    return out


def _mf_scores_for_cards(
    org_id: str,
    cards: list[dict[str, Any]],
    *,
    actor_id: str | None,
    settings: Any | None,
    factorizer: Any | None,
) -> tuple[dict[str, float] | None, str]:
    """Load org MF artifact and score card item keys. Falls back to affinity-only."""
    model = factorizer
    if model is None:
        try:
            import asyncio

            from app.ml.model_catalog import load_org_trained_catalog_model

            async def _load():
                return await load_org_trained_catalog_model(
                    org_id, "cf_matrix_factorizer", settings=settings
                )

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Sync route path — skip async load; affinity-only until tip trains via admin.
                model = None
            else:
                model = asyncio.run(_load())
        except Exception as exc:  # noqa: BLE001
            logger.debug("cf_mf_load_skipped org_id=%s err=%s", org_id, exc)
            model = None

    if model is None or not getattr(model, "is_trained", False):
        return None, "item_affinity"

    item_keys: list[str] = []
    for card in cards:
        item_keys.extend(card_item_keys(card))
    scores = model.score_items(actor_id=actor_id, org_id=org_id, item_keys=item_keys)
    if not scores:
        return None, "item_affinity"
    return scores, "matrix_factorization"


async def soft_rank_heuristic_payload_async(
    client: Any,
    org_id: str,
    payload: dict[str, Any],
    *,
    lookback_days: int = LOOKBACK_DAYS,
    actor_id: str | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Async variant that can load trained MF artifacts from the registry."""
    factorizer = None
    try:
        from app.ml.model_catalog import load_org_trained_catalog_model

        loaded = await load_org_trained_catalog_model(
            org_id, "cf_matrix_factorizer", settings=settings
        )
        if getattr(loaded, "is_trained", False):
            factorizer = loaded
    except Exception as exc:  # noqa: BLE001
        logger.debug("cf_mf_async_load_skipped org_id=%s err=%s", org_id, exc)

    return soft_rank_heuristic_payload(
        client,
        org_id,
        payload,
        lookback_days=lookback_days,
        actor_id=actor_id,
        settings=settings,
        factorizer=factorizer,
    )


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
