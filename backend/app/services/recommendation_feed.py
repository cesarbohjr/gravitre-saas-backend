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

Account items read account health's rules (``account_health.read_observations``
and ``signal_dims``), the same reading the health page and the chat/voice card
use. With ACCOUNT_FEED_UNIFIED_V1 the feed shows one item per account built
from full account health, with the churn advisory merged in; where the churn
model and the customers' own churn-risk language disagree, both are shown with
their basis.
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
# Wording for an account change. Which changes surface is decided by
# account_health.read_observations (``notable``), not here.
_ACCOUNT_CHANGES = {
    "sentiment": "Sentiment is falling",
    "churn_risk_language": "Churn-risk language is rising",
    "support_friction": "Support friction is rising",
    "urgency": "Urgency is rising",
    "expansion_interest": "Expansion interest is rising",
}
_SIGNAL_FOR_DIM = {"contact_volume": "contact_volume_change", "contact_gap": "contact_gap_days"}
_FLAGGED = ("at_risk", "watch")
_STATUS_WORDS = {"at_risk": "at risk", "watch": "watch"}


def feed_enabled(settings: Any) -> bool:
    return getattr(settings, "recommendation_feed_enabled", False) is True


def unified_accounts_enabled(settings: Any) -> bool:
    return getattr(settings, "account_feed_unified_v1", False) is True


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
                extra={"workObjectId": r.get("id"), "goalId": r.get("goal_id"), "businessEntityId": r.get("business_entity_id"), "playKey": proposal.get("play_key")},
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
    """Account changes with enough evidence: trends from observations, rule-based behaviour.

    Which changes surface and which quotes back them is account health's reading
    (``account_health.read_observations`` / ``signal_dims``); this only words them.
    """
    from app.services.account_health import (
        latest_signals,
        quote_line,
        read_observations,
        signal_dims,
    )

    now = now or datetime.now(UTC)
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in observations:
        by_entity[str(o.get("entity_id"))].append(o)
    out = []
    for eid, rows in by_entity.items():
        name = entities.get(eid)
        if not name:
            continue
        for reading in read_observations(rows, now=now):
            if not reading["notable"]:
                continue
            dim, t, label = reading["key"], reading["trend"], _ACCOUNT_CHANGES[reading["key"]]
            quotes = [quote_line(q) for q in reading["quotes"]][:3]
            negative = not reading["opportunity"]
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
    sig_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in signals:
        sig_by[str(s.get("entity_id"))].append(s)
    for eid, rows in sig_by.items():
        name = entities.get(eid)
        if not name:
            continue
        latest = latest_signals(rows)
        for d in signal_dims(rows):
            if d["status"] not in _FLAGGED:
                continue
            s = latest[_SIGNAL_FOR_DIM[d["key"]]]
            out.append(_signal_item(eid, name, s))
    return out


def _signal_item(eid: str, name: str, s: dict[str, Any]) -> dict[str, Any]:
    value = float(s.get("value") or 0)
    if s.get("signal") == "contact_volume_change":
        title, why, urgency = f"{name}: contact volume is {value:.1f}x usual", "Last 14 days against the prior 8 weeks.", 0.65
    else:
        title, why, urgency = f"{name}: no customer message for {round(value)} days", "Measured from the last customer message.", 0.45
    return _item(
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


# --------------------------------------------------------------------------- unified accounts (ACCOUNT_FEED_UNIFIED_V1)

_CHURN_SOURCE = "churn_model"
_HEALTH_SOURCE = "account_health"


def _churn_reading(card: dict[str, Any]) -> dict[str, Any]:
    ev = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
    level = str(ev.get("riskLevel") or "unknown")
    factors = [str(f) for f in ev.get("contributingFactors") or []][:3]
    trained = card.get("_trained") is True
    basis = (
        f"Churn model score {float(ev.get('riskScore') or 0):.2f} from account usage features"
        + (", trained on this organisation's outcomes" if trained else ", untrained (no outcomes from this organisation yet)")
        + (f"; factors: {', '.join(factors)}" if factors else "")
    )
    return {"source": _CHURN_SOURCE, "reading": level, "basis": basis}


def _language_reading(dim: dict[str, Any] | None) -> dict[str, Any] | None:
    if not dim:
        return None
    cov = dim.get("coverage") or {}
    value = dim.get("value") if isinstance(dim.get("value"), dict) else {}
    if dim.get("status") == "unknown":
        basis = f"Not enough customer messages yet ({cov.get('observations', 0)} observations)"
    else:
        basis = (
            f"Churn-risk language {value.get('direction')} in customer messages, "
            f"{cov.get('observations')} observations across {cov.get('messages')} messages over {cov.get('window_days')} days"
        )
    return {"source": "entity_observations", "reading": str(dim.get("status")), "basis": basis}


def churn_disagreement(churn_level: str, language_status: str | None) -> bool:
    """The churn model and the customers' own words point different ways.

    Sentiment is evidence, not truth, and the model is a score, not a fact: when
    they disagree the feed shows both with their basis and picks neither.
    """
    if language_status in {None, "unknown"}:
        return False
    if churn_level == "high":
        return language_status == "healthy"
    if churn_level == "low":
        return language_status in _FLAGGED
    return False


def items_from_account_health(
    healths: list[dict[str, Any]],
    churn_cards: list[dict[str, Any]] | None = None,
    *,
    entity_for_customer: dict[str, str] | None = None,
    names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One item per account: account health's flagged dimensions plus the churn model.

    Each evidence line names its source. Churn advisory cards are matched to an
    account by id (or a bound provider record); unmatched elevated ones stay as
    their own item.
    """
    entity_for_customer = entity_for_customer or {}
    names = dict(names or {})
    by_entity: dict[str, dict[str, Any]] = {}
    for h in healths:
        eid = str((h.get("entity") or {}).get("id") or "")
        if eid:
            by_entity[eid] = h
            names.setdefault(eid, str((h.get("entity") or {}).get("name") or ""))
    churn_by_entity: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for card in churn_cards or []:
        if card.get("kind") != "churn_risk_advisory":
            continue  # pending cards say a model is not trained yet; nothing to act on
        cid = str((card.get("evidence") or {}).get("customerId") or "")
        eid = cid if cid in by_entity or cid in names else entity_for_customer.get(cid, "")
        if eid:
            churn_by_entity.setdefault(eid, card)
        else:
            unmatched.append(card)

    out: list[dict[str, Any]] = []
    for eid in sorted(set(by_entity) | set(churn_by_entity)):
        name = names.get(eid)
        if not name:
            continue
        dims = (by_entity.get(eid) or {}).get("dimensions") or []
        flagged = [d for d in dims if d.get("status") in _FLAGGED]
        opportunities = [d for d in dims if d.get("note") == "Opportunity."]
        card = churn_by_entity.get(eid)
        churn = _churn_reading(card) if card else None
        language_dim = next((d for d in dims if d.get("key") == "churn_risk_language"), None)
        language = _language_reading(language_dim)
        disagree = bool(churn) and churn_disagreement(churn["reading"], (language_dim or {}).get("status"))
        churn_elevated = bool(churn) and churn["reading"] in {"high", "medium"}
        if not (flagged or opportunities or churn_elevated or disagree):
            continue
        evidence: list[str] = []
        for d in sorted(flagged, key=lambda d: d["status"] != "at_risk")[:3]:
            if d["key"] in _ACCOUNT_CHANGES:
                value = d.get("value") if isinstance(d.get("value"), dict) else {}
                detail = f"{value.get('direction')}, {(d.get('coverage') or {}).get('observations')} observations"
            else:
                detail = (d.get("evidence") or [""])[0]
            evidence.append(f"[account health] {d['label']}: {_STATUS_WORDS[d['status']]}" + (f" ({detail})" if detail else ""))
        for d in opportunities[:1]:
            evidence.append(f"[account health] {d['label']}: rising (opportunity)")
        if churn:
            evidence.append(f"[churn model] {churn['reading']} churn risk. {churn['basis']}")
        quote = next((d["evidence"][0] for d in flagged if d["key"] in _ACCOUNT_CHANGES and d.get("evidence")), None)
        if quote:
            evidence.append(f"[customer message] {quote}")
        at_risk = [d["label"] for d in flagged if d["status"] == "at_risk"]
        watch = [d["label"] for d in flagged if d["status"] == "watch"]
        parts = []
        if at_risk:
            parts.append(f"{', '.join(at_risk).lower()} at risk")
        if watch:
            parts.append(f"{', '.join(watch).lower()} to watch")
        if churn_elevated:
            parts.append(f"{churn['reading']} churn risk (model)")
        if not parts and opportunities:
            parts.append("expansion interest is rising")
        if not parts:
            parts.append("churn signals disagree")
        why = "Per-dimension account health (no composite score)."
        readings = [r for r in (churn, language) if r] if churn else []
        if disagree:
            why = (
                f"The churn model reads {churn['reading']} risk but customer messages read "
                f"{_STATUS_WORDS.get(language['reading'], language['reading'])} for churn-risk language. "
                "Both are shown with their basis; neither overrides the other."
            )
        severe = bool(at_risk) or (bool(churn) and churn["reading"] == "high")
        obs_counts = [int((d.get("coverage") or {}).get("observations") or 0) for d in flagged + opportunities if d["key"] in _ACCOUNT_CHANGES]
        sources = [s for s, present in ((_HEALTH_SOURCE, bool(flagged or opportunities)), (_CHURN_SOURCE, bool(churn))) if present]
        out.append(
            _item(
                item_id=f"account:{eid}",
                kind="account_health",
                title=f"{name}: {'; '.join(parts)}",
                why=why,
                evidence=evidence,
                source="+".join(sources) or _HEALTH_SOURCE,
                # confidence-honesty-ok: ranking weight only (evidence volume), never shown as a confidence
                axes={
                    "impact": 0.8 if severe else 0.6,
                    "urgency": 0.7 if severe else (0.5 if flagged or churn_elevated else 0.4),
                    "confidence": min(1.0, 0.3 + 0.07 * max(obs_counts)) if obs_counts else 0.5,
                    "relevance": 0.8,
                    "actionability": 0.6,
                    "novelty": 0.8,
                },
                href="/intelligence/predictive",
                extra={
                    "businessEntityId": eid,
                    "sources": sources,
                    "dimensions": [{"key": d["key"], "status": d["status"]} for d in flagged],
                    "readings": readings,
                    "disagreement": disagree,
                },
            )
        )
    for card in unmatched:
        churn = _churn_reading(card)
        if churn["reading"] not in {"high", "medium"}:
            continue
        cid = str((card.get("evidence") or {}).get("customerId") or "")
        out.append(
            _item(
                item_id=f"churn:{cid}",
                kind="account_health",
                title=str(card.get("title") or f"Account {cid}: {churn['reading']} churn risk"),
                why="Not linked to a filed account, so customer messages could not be compared.",
                evidence=[f"[churn model] {churn['reading']} churn risk. {churn['basis']}", str(card.get("reason") or "")],
                source=_CHURN_SOURCE,
                # confidence-honesty-ok: fixed ranking weight, never shown as a confidence
                axes={
                    "impact": 0.8 if churn["reading"] == "high" else 0.6,
                    "urgency": 0.6,
                    "confidence": 0.5,
                    "relevance": 0.7,
                    "actionability": 0.5,
                    "novelty": 0.7,
                },
                href="/intelligence/predictive",
                extra={"customerId": cid, "sources": [_CHURN_SOURCE], "readings": [churn], "disagreement": False},
            )
        )
    return out


def _entity_for_customers(client: Any, org_id: str, customer_ids: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Map churn customer ids to filed accounts: by entity id, else by a bound provider record."""
    ids = sorted({c for c in customer_ids if c})[:200]
    if not ids:
        return {}, {}
    mapping: dict[str, str] = {}
    direct = client.table("org_business_entities").select("id, display_name").eq("org_id", org_id).in_("id", ids).execute().data or []
    names = {str(r["id"]): str(r.get("display_name") or "") for r in direct}
    for cid in ids:
        if cid in names:
            mapping[cid] = cid
    rest = [c for c in ids if c not in mapping]
    if rest:
        bound = (
            client.table("org_business_entity_bindings")
            .select("entity_id, resource_id")
            .eq("org_id", org_id)
            .in_("resource_id", rest)
            .execute()
            .data
            or []
        )
        for b in bound:
            mapping.setdefault(str(b.get("resource_id")), str(b.get("entity_id")))
        missing = sorted({e for e in mapping.values() if e not in names})
        if missing:
            rows = client.table("org_business_entities").select("id, display_name").eq("org_id", org_id).in_("id", missing).execute().data or []
            names.update({str(r["id"]): str(r.get("display_name") or "") for r in rows})
    return {c: e for c, e in mapping.items() if e in names}, names


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
        from app.services.entity_observations import observations_enabled

        if not observations_enabled(settings):
            raise _Skipped()
        from app.services.memory_source_liveness import (
            drop_observations_from_revoked_sources,
            observation_columns,
        )

        since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        obs = (
            client.table("entity_observations")
            .select(
                observation_columns(
                    "entity_id, dimension, label, score, evidence_quote, source_system, source_record_id, observed_at, status, correction",
                    settings,
                )
            )
            .eq("org_id", org_id)
            .gte("observed_at", since)
            .limit(3000)
            .execute()
            .data
            or []
        )
        sig = (
            client.table("entity_behavior_signals")
            .select("entity_id, signal, value, baseline, evidence_count, rule_version, window_end")
            .eq("org_id", org_id)
            .gte("window_end", (datetime.now(UTC) - timedelta(days=2)).date().isoformat())
            .limit(1000)
            .execute()
            .data
            or []
        )
        obs, sig = drop_observations_from_revoked_sources(client, org_id, obs, sig, settings=settings)
        ids = sorted({str(r.get("entity_id")) for r in obs + sig if r.get("entity_id")})[:200]
        names: dict[str, str] = {}
        if ids:
            rows = client.table("org_business_entities").select("id, display_name").eq("org_id", org_id).in_("id", ids).execute().data or []
            names = {str(r["id"]): str(r.get("display_name") or "") for r in rows}
        return items_from_accounts(names, obs, sig)

    unified = unified_accounts_enabled(settings)
    healths: list[dict[str, Any]] = []

    def _account_health() -> list[dict[str, Any]]:
        from app.services.account_health import load_health_batch

        if getattr(settings, "entity_observations_enabled", False) is not True:
            raise _Skipped()
        healths.extend(load_health_batch(client, org_id, settings=settings))
        return []  # items are built once churn advisory is in, one per account

    try:
        items += await _signals()
        sources["business_signals"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("recommendation_feed_source_failed source=business_signals error=%s", type(exc).__name__)
        sources["business_signals"] = "error"
    for name, fn in (
        ("heuristic_cards", _cards),
        ("proposals", _proposals),
        ("accounts", _account_health if unified else _accounts),
    ):
        try:
            items += await asyncio.to_thread(fn)
            sources[name] = "ok"
        except _Skipped:
            sources[name] = "off"
        except Exception as exc:  # noqa: BLE001
            logger.warning("recommendation_feed_source_failed source=%s error=%s", name, type(exc).__name__)
            sources[name] = "error"

    if unified:
        churn_cards: list[dict[str, Any]] = []
        try:
            from app.services.churn_advisory_service import build_churn_advisory_cards

            # Read-only here: predictions are logged by the churn advisory surface itself.
            payload = await build_churn_advisory_cards(org_id, settings=settings, client=client, limit=50, log_predictions=False)
            trained = payload.get("trained") is True
            churn_cards = [{**c, "_trained": trained} for c in payload.get("recommendations") or [] if isinstance(c, dict)]
            sources["churn_advisory"] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("recommendation_feed_source_failed source=churn_advisory error=%s", type(exc).__name__)
            sources["churn_advisory"] = "error"
        try:
            customer_ids = [str((c.get("evidence") or {}).get("customerId") or "") for c in churn_cards]
            known = {str((h.get("entity") or {}).get("id")) for h in healths}
            mapping, names = await asyncio.to_thread(
                _entity_for_customers, client, org_id, [c for c in customer_ids if c not in known]
            )
            items += items_from_account_health(healths, churn_cards, entity_for_customer=mapping, names=names)
        except Exception as exc:  # noqa: BLE001
            logger.warning("recommendation_feed_source_failed source=account_merge error=%s", type(exc).__name__)
            sources["accounts"] = "error"

    seen: set[str] = set()
    ranked = []
    for it in sorted(items, key=lambda i: i["score"], reverse=True):
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        from app.services.intelligence_remedies import remedies_for_recommendation

        it["remedies"] = remedies_for_recommendation(it)
        ranked.append(it)
    return {"items": ranked[:MAX_ITEMS], "sources": sources, "generatedAt": datetime.now(UTC).isoformat()}


class _Skipped(Exception):
    pass
