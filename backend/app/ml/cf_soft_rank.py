"""CF v1 soft-rank — reorder heuristic cards by item affinity; never drop cards."""
from __future__ import annotations

from typing import Any

from app.ml.cf_interaction_ingest import (
    item_key_card,
    item_key_connector,
    item_key_pack,
)


def card_item_keys(card: dict[str, Any]) -> list[str]:
    """Map a heuristic card to CF item keys (card + connector/pack evidence)."""
    keys: list[str] = []
    card_id = str(card.get("id") or "").strip()
    if card_id:
        keys.append(item_key_card(card_id))
    evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
    vendor = str(evidence.get("vendor") or "").strip().lower()
    if vendor:
        keys.append(item_key_connector(vendor))
    pack_id = str(
        evidence.get("suggestedPackId")
        or evidence.get("packId")
        or evidence.get("pack_id")
        or evidence.get("suggestedPack")
        or ""
    ).strip().lower()
    if pack_id:
        keys.append(item_key_pack(pack_id))
    # pack-{vendor}-{pack_id} card ids
    if card_id.startswith("pack-"):
        parts = card_id.split("-", 2)
        if len(parts) >= 3:
            keys.append(item_key_connector(parts[1]))
            keys.append(item_key_pack(parts[2]))
    elif card_id.startswith("unused-") or card_id.startswith("nonexec-"):
        vendor_from_id = card_id.split("-", 1)[-1].strip().lower()
        if vendor_from_id:
            keys.append(item_key_connector(vendor_from_id))
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def score_card(
    card: dict[str, Any],
    affinity: dict[str, float],
    *,
    mf_scores: dict[str, float] | None = None,
    mf_weight: float = 0.7,
) -> float:
    keys = card_item_keys(card)
    if not keys:
        return 0.0
    affinity_score = float(max(float(affinity.get(k) or 0.0) for k in keys))
    if not mf_scores:
        return affinity_score
    mf_score = float(max(float(mf_scores.get(k) or 0.0) for k in keys))
    # Blend MF latent score with item affinity (fallback for unseen items).
    w = min(1.0, max(0.0, float(mf_weight)))
    return (w * mf_score) + ((1.0 - w) * affinity_score)


def soft_rank_cards(
    cards: list[dict[str, Any]],
    affinity: dict[str, float],
    *,
    mf_scores: dict[str, float] | None = None,
    method: str = "item_affinity",
) -> list[dict[str, Any]]:
    """Stable soft-rank by CF affinity / MF. Never drops cards. Advisory annotations only."""
    indexed = list(enumerate(cards))
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, card in indexed:
        cf_score = score_card(card, affinity, mf_scores=mf_scores)
        enriched = dict(card)
        enriched["cf_score"] = round(cf_score, 4)
        enriched["cf_ranked"] = True
        enriched["cf_method"] = method
        scored.append((cf_score, idx, enriched))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in scored]
