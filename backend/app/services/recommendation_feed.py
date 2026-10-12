"""Phase 5: one ranked recommendation feed.

Recommendations come from several producers (business signals, heuristic
suggestion cards, AI-proposed work, and now customer-account changes). This
feed reads each of them through its existing path and ranks everything on the
same attention axes the proactive operator uses, so the UI can show one list
with the evidence behind every item. Nothing here executes anything: items are
advisory, and the only actions are the producers' own (accept or dismiss a
proposal, dismiss a card, open a link).

Each producer is read independently. One that fails or is switched off is
reported in ``sources`` and the rest of the feed still renders. Existing
recommendation surfaces are untouched.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.proactive_business_operator import _rank_score

logger = get_logger(__name__)

MAX_ITEMS = 20
_IMPACT = {"high": 0.9, "medium": 0.55, "low": 0.2}
_PRIORITY_IMPACT = {"critical": 0.95, "high": 0.8, "medium": 0.55, "low": 0.25}
# Account changes worth surfacing: (dimension, direction) pairs.
_ACCOUNT_CHANGES = {
    ("sentiment", "falling"): "Sentiment is falling",
    ("churn_risk_language", "rising"): "Churn-risk language is rising",
    ("support_friction", "rising"): "Support friction is rising",
    ("urgency", "rising"): "Urgency is rising",
    ("expansion_interest", "rising"): "Expansion interest is rising",
}
VOLUME_SPIKE = 2.0
GAP_DAYS = 30


def feed_enabled(settings: Any) -> bool:
    return getattr(settings, "recommendation_feed_enabled", False) is True


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _item(
    *,
    item_id: str,
    kind: str,
    title: str,
    why: str,
    evidence: list[str],
    source: str,
    axes: dict[str, float],
    href: str | None = None,
    actions: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "title": title[:200],
        "why": why[:500],
        "evidence": [e[:300] for e in evidence if e][:5],
        "source": source,
        "axes": {k: round(v, 3) for k, v in axes.items()},
        "score": _rank_score(axes),
        "href": href,
        "actions": actions or [],
        "advisoryOnly": True,
        **(extra or {}),
    }


def items_from_business_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for s in signals:
        if not isinstance(s, dict) or not s.get("title"):
            continue
        risk = str(s.get("signal_type") or "") in {"risk", "warning", "alert"}
        out.append(
            _item(
                item_id=f"signal:{s.get('id')}",
                kind="business_signal",
                title=str(s["title"]),
                why=str(s.get("summary") or ""),
                evidence=[str(s.get("summary") or "")],
                source=str(s.get("source") or "business_signals"),
                axes={
                    "impact": _IMPACT.get(str(s.get("estimated_impact") or "").lower(), 0.4),
                    "urgency": 0.6 if risk else 0.35,
                    "confidence": _float(s.get("confidence"), 0.3),
                    "relevance": 0.7,
                    "actionability": 0.5,
                    "novelty": 0.8,
                },
            )
        )
    return out


def items_from_heuristic_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in cards:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        evidence = c.get("evidence") if isinstance(c.get("evidence"), dict) else {}
        priority = int(c.get("priority") or 3)
        out.append(
            _item(
                item_id=f"card:{c['id']}",
                kind="suggestion",
                title=str(c.get("title") or ""),
                why=str(c.get("reason") or ""),
                evidence=[f"{k}: {v}" for k, v in list(evidence.items())[:3]],
                source="heuristic_cards",
                axes={
                    "impact": max(0.2, 0.9 - 0.15 * (priority - 1)),
                    "urgency": 0.3,
                    "confidence": _float(c.get("confidence"), 0.3),
                    "relevance": 0.6,
                    "actionability": 0.7,
                    "novelty": 0.6,
                },
                href=c.get("href"),
                actions=["dismiss"],
                extra={"cardId": c["id"]},
            )
        )
    return out


def items_from_proposals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        proposal = safe_normalize_stored_dict(safe_normalize_stored_dict(r.get("metadata")), key="proposal")
        ev = [str(e.get("summary") or e.get("quote") or e) if isinstance(e, dict) else str(e) for e in proposal.get("evidence") or []]
        out.append(
            _item(
                item_id=f"proposal:{r.get('id')}",
                kind="proposed_work",
                title=str(r.get("title") or ""),
                why=str(r.get("objective") or "Proposed from your connected data."),
                evidence=ev,
                source=str(proposal.get("source") or "proposals"),
                axes={
                    "impact": _PRIORITY_IMPACT.get(str(r.get("priority") or "medium"), 0.55),
                    "urgency": 0.5,
                    "confidence": min(1.0, 0.35 + 0.15 * len(ev)),
                    "relevance": 0.8,
                    "actionability": 0.9,
                    "novelty": 0.7,
                },
                href="/activity?tab=objects",
                actions=["accept", "dismiss"],
                extra={"workObjectId": r.get("id"), "goalId": r.get("goal_id"), "businessEntityId": r.get("business_entity_id")},
            )
        )
    return out


def items_from_accounts(
    entities: dict[str, str],
    observations: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Account changes with enough evidence: trends from observations, rule-based behaviour."""
    from app.services.entity_observations import trend

    now = now or datetime.now(UTC)
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in observations:
        by_entity[str(o.get("entity_id"))].append(o)
    out = []
    for eid, rows in by_entity.items():
        name = entities.get(eid)
        if not name:
            continue
        for (dim, direction), label in _ACCOUNT_CHANGES.items():
            t = trend(rows, dimension=dim, now=now)
            if t["direction"] != direction:
                continue
            quotes = [
                f'"{r.get("evidence_quote")}" ({r.get("source_system")})'
                for r in sorted(rows, key=lambda r: str(r.get("observed_at")), reverse=True)
                if r.get("dimension") == dim and r.get("status") != "retracted"
            ][:3]
            negative = (dim, direction) != ("expansion_interest", "rising")
            out.append(
                _item(
                    item_id=f"account:{eid}:{dim}",
                    kind="account_change",
                    title=f"{name}: {label.lower()}",
                    why=f"{t['observations']} observations from {t['sources']} messages over 30 days, change {t.get('delta')}.",
                    evidence=quotes,
                    source="entity_observations",
                    axes={
                        "impact": 0.75 if negative else 0.6,
                        "urgency": 0.7 if negative else 0.4,
                        "confidence": min(1.0, 0.3 + 0.07 * t["observations"]),
                        "relevance": 0.8,
                        "actionability": 0.6,
                        "novelty": 0.8,
                    },
                    href="/intelligence/predictive",
                    extra={"businessEntityId": eid, "dimension": dim},
                )
            )
    for s in signals:
        eid = str(s.get("entity_id"))
        name = entities.get(eid)
        value = float(s.get("value") or 0)
        if not name:
            continue
        if s.get("signal") == "contact_volume_change" and value >= VOLUME_SPIKE:
            title, why, urgency = f"{name}: contact volume is {value:.1f}x usual", "Last 14 days against the prior 8 weeks.", 0.65
        elif s.get("signal") == "contact_gap_days" and value >= GAP_DAYS:
            title, why, urgency = f"{name}: no customer message for {round(value)} days", "Measured from the last customer message.", 0.45
        else:
            continue
        out.append(
            _item(
                item_id=f"account:{eid}:{s.get('signal')}",
                kind="account_change",
                title=title,
                why=why,
                evidence=[f"{s.get('signal')}={value:g} (rule {s.get('rule_version') or 'beh-v1'})"],
                source="entity_behavior_signals",
                # confidence-honesty-ok: fixed ranking weight for a rule-based signal, never shown as a confidence
                axes={"impact": 0.6, "urgency": urgency, "confidence": 0.6, "relevance": 0.8, "actionability": 0.5, "novelty": 0.7},
                href="/intelligence/predictive",
                extra={"businessEntityId": eid, "signal": s.get("signal")},
            )
        )
    return out


async def build_feed(client: Any, settings: Any, *, org_id: str, user_id: str | None, department: str | None = None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    sources: dict[str, str] = {}

    async def _signals() -> list[dict[str, Any]]:
        from app.services.business_signals_engine import get_business_signals_engine

        payload = await get_business_signals_engine(settings).collect_signals(
            org_id, department=department, client=client, include_predictive=False
        )
        return items_from_business_signals(payload.get("signals") or [])

    def _cards() -> list[dict[str, Any]]:
        from app.services.recommendation_heuristics_service import (
            build_heuristic_recommendations,
            filter_dismissed_recommendations,
            load_dismissed_card_ids,
            load_heuristic_signals,
        )

        sig = load_heuristic_signals(client, org_id)
        payload = build_heuristic_recommendations(
            connected_connectors=sig["connected_connectors"],
            usage_by_connector=sig["usage_by_connector"],
            installed_packs=sig["installed_packs"],
            lookback_days=int(sig.get("lookback_days") or 30),
        )
        if user_id:
            payload = filter_dismissed_recommendations(payload, load_dismissed_card_ids(client, org_id, user_id))
        return items_from_heuristic_cards(payload.get("recommendations") or [])

    def _proposals() -> list[dict[str, Any]]:
        from app.services.work_object_proposals import proposals_enabled

        if not proposals_enabled(settings):
            raise _Skipped()
        rows = (
            client.table("work_objects")
            .select("id, title, objective, priority, metadata, goal_id, business_entity_id")
            .eq("org_id", org_id)
            .eq("status", "proposed")
            .limit(50)
            .execute()
            .data
            or []
        )
        return items_from_proposals(rows)

    def _accounts() -> list[dict[str, Any]]:
        if getattr(settings, "entity_observations_enabled", False) is not True:
            raise _Skipped()
        since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        obs = (
            client.table("entity_observations")
            .select("entity_id, dimension, score, evidence_quote, source_system, source_record_id, observed_at, status, correction")
            .eq("org_id", org_id)
            .gte("observed_at", since)
            .limit(3000)
            .execute()
            .data
            or []
        )
        sig = (
            client.table("entity_behavior_signals")
            .select("entity_id, signal, value, rule_version, window_end")
            .eq("org_id", org_id)
            .gte("window_end", (datetime.now(UTC) - timedelta(days=2)).date().isoformat())
            .limit(1000)
            .execute()
            .data
            or []
        )
        ids = sorted({str(r.get("entity_id")) for r in obs + sig if r.get("entity_id")})[:200]
        names: dict[str, str] = {}
        if ids:
            rows = client.table("org_business_entities").select("id, display_name").eq("org_id", org_id).in_("id", ids).execute().data or []
            names = {str(r["id"]): str(r.get("display_name") or "") for r in rows}
        return items_from_accounts(names, obs, sig)

    try:
        items += await _signals()
        sources["business_signals"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("recommendation_feed_source_failed source=business_signals error=%s", type(exc).__name__)
        sources["business_signals"] = "error"
    for name, fn in (("heuristic_cards", _cards), ("proposals", _proposals), ("accounts", _accounts)):
        try:
            items += await asyncio.to_thread(fn)
            sources[name] = "ok"
        except _Skipped:
            sources[name] = "off"
        except Exception as exc:  # noqa: BLE001
            logger.warning("recommendation_feed_source_failed source=%s error=%s", name, type(exc).__name__)
            sources[name] = "error"

    seen: set[str] = set()
    ranked = []
    for it in sorted(items, key=lambda i: i["score"], reverse=True):
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        ranked.append(it)
    return {"items": ranked[:MAX_ITEMS], "sources": sources, "generatedAt": datetime.now(UTC).isoformat()}


class _Skipped(Exception):
    pass
