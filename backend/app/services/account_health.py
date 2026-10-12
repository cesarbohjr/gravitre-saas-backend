"""Phase 7: explainable account health, one dimension at a time.

There is deliberately no composite score. Each dimension has a written
definition, says whether it is a leading or lagging indicator, gives its
status (``healthy`` / ``watch`` / ``at_risk`` / ``unknown``) by a stated rule,
and carries the evidence and coverage behind it. A dimension without enough
evidence is ``unknown``, never a guess.

Inputs are the stores the platform already keeps: customer observations
(Phase 3), rule-based behaviour signals, and work objects linked to the
account (Phase 5).

Off (404) unless ACCOUNT_HEALTH_ENABLED is true.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.entity_observations import trend

WINDOW_DAYS = 30
GAP_WATCH_DAYS = 30
GAP_RISK_DAYS = 60
VOLUME_WATCH = 2.0
MEAN_WATCH = 0.3

DEFINITIONS: dict[str, dict[str, str]] = {
    "sentiment": {
        "label": "Customer sentiment",
        "kind": "leading",
        "definition": "Tone of inbound customer messages over 30 days (-1 negative to 1 positive), "
        "from at least 5 observations across 3 messages. At risk when falling; watch when the recent mean is below 0.",
    },
    "churn_risk_language": {
        "label": "Churn-risk language",
        "kind": "leading",
        "definition": "Mentions of cancelling, switching or not renewing (0 none to 1 explicit). "
        "At risk when rising; watch when the recent mean is above 0.3.",
    },
    "support_friction": {
        "label": "Support friction",
        "kind": "leading",
        "definition": "Complaints about problems, delays or repeat issues (0 none to 1 severe). "
        "At risk when rising; watch when the recent mean is above 0.3.",
    },
    "urgency": {
        "label": "Urgency",
        "kind": "leading",
        "definition": "How time-pressed inbound requests are (0 none to 1 immediate). Watch when rising.",
    },
    "expansion_interest": {
        "label": "Expansion interest",
        "kind": "leading",
        "definition": "Interest in more seats, products or scope (0 none to 1 explicit). "
        "Rising is an opportunity, shown as healthy.",
    },
    "contact_volume": {
        "label": "Contact volume",
        "kind": "leading",
        "definition": "Customer messages in the last 14 days against the weekly rate of the 8 weeks before "
        "(rule beh-v1; needs 4 earlier messages). Watch at 2x or more.",
    },
    "contact_gap": {
        "label": "Time since last contact",
        "kind": "leading",
        "definition": "Days since the last customer message (rule beh-v1; needs 3 messages in 90 days). "
        "Watch at 30 days, at risk at 60.",
    },
    "open_work": {
        "label": "Linked work",
        "kind": "lagging",
        "definition": "Work objects linked to this account. Watch when any is blocked or failed.",
    },
}


def health_enabled(settings: Any) -> bool:
    return getattr(settings, "account_health_enabled", False) is True


def _dim(key: str, status: str, value: Any, evidence: list[str], coverage: dict[str, Any], note: str = "") -> dict[str, Any]:
    d = DEFINITIONS[key]
    return {
        "key": key,
        "label": d["label"],
        "kind": d["kind"],
        "definition": d["definition"],
        "status": status,
        "value": value,
        "note": note or None,
        "evidence": evidence[:3],
        "coverage": coverage,
    }


def _observation_dims(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    out = []
    for key in ("sentiment", "churn_risk_language", "support_friction", "urgency", "expansion_interest"):
        t = trend(rows, dimension=key, now=now, window_days=WINDOW_DAYS)
        coverage = {"observations": t["observations"], "messages": t["sources"], "window_days": WINDOW_DAYS}
        quotes = [
            f'"{r.get("evidence_quote")}" ({r.get("source_system")}, {str(r.get("observed_at"))[:10]})'
            for r in sorted(rows, key=lambda r: str(r.get("observed_at")), reverse=True)
            if r.get("dimension") == key and r.get("status") != "retracted" and r.get("label") not in {"neutral", "none"}
        ]
        direction = t["direction"]
        if direction == "insufficient_evidence":
            out.append(_dim(key, "unknown", None, quotes, coverage, "Not enough observations yet."))
            continue
        mean = t.get("latest_mean")
        value = {"direction": direction, "recent_mean": mean, "change": t.get("delta")}
        if key == "sentiment":
            status = "at_risk" if direction == "falling" else ("watch" if (mean or 0) < 0 else "healthy")
        elif key in {"churn_risk_language", "support_friction"}:
            status = "at_risk" if direction == "rising" else ("watch" if (mean or 0) > MEAN_WATCH else "healthy")
        elif key == "urgency":
            status = "watch" if direction == "rising" else "healthy"
        else:
            status = "healthy"
        note = "Opportunity." if key == "expansion_interest" and direction == "rising" else ""
        out.append(_dim(key, status, value, quotes, coverage, note))
    return out


def _signal_dims(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for s in sorted(signals, key=lambda s: str(s.get("window_end")), reverse=True):
        latest.setdefault(str(s.get("signal")), s)
    out = []
    vol = latest.get("contact_volume_change")
    if vol is None:
        out.append(_dim("contact_volume", "unknown", None, [], {}, "Not enough message history yet."))
    else:
        v = float(vol.get("value") or 0)
        out.append(_dim("contact_volume", "watch" if v >= VOLUME_WATCH else "healthy", round(v, 2),
                        [f"{v:.1f}x usual, baseline {vol.get('baseline')} per 14 days"],
                        {"messages": vol.get("evidence_count"), "as_of": vol.get("window_end")}))
    gap = latest.get("contact_gap_days")
    if gap is None:
        out.append(_dim("contact_gap", "unknown", None, [], {}, "Not enough message history yet."))
    else:
        g = float(gap.get("value") or 0)
        status = "at_risk" if g >= GAP_RISK_DAYS else "watch" if g >= GAP_WATCH_DAYS else "healthy"
        out.append(_dim("contact_gap", status, round(g), [f"last customer message {round(g)} days ago"],
                        {"messages": gap.get("evidence_count"), "as_of": gap.get("window_end")}))
    return out


def _work_dim(work: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [w for w in work if w.get("status") not in {"proposed", "archived"}]
    if not counted:
        return _dim("open_work", "unknown", None, [], {"linked": 0}, "No work linked to this account.")
    troubled = [w for w in counted if w.get("status") in {"blocked", "failed"}]
    by_status: dict[str, int] = defaultdict(int)
    for w in counted:
        by_status[str(w.get("status"))] += 1
    return _dim(
        "open_work",
        "watch" if troubled else "healthy",
        dict(by_status),
        [f"{w.get('title')} is {w.get('status')}" for w in troubled],
        {"linked": len(counted)},
    )


def build_account_health(
    entity: dict[str, Any],
    observations: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    work: list[dict[str, Any]],
    *,
    systems: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    dims = _observation_dims(observations, now) + _signal_dims(signals) + [_work_dim(work)]
    counts: dict[str, int] = defaultdict(int)
    for d in dims:
        counts[d["status"]] += 1
    return {
        "entity": {"id": entity.get("id"), "name": entity.get("display_name"), "systems": systems or []},
        "dimensions": dims,
        "statusCounts": dict(counts),
        "compositeScore": None,  # by design: no composite until a written methodology is approved
        "generatedAt": now.isoformat(),
    }


def load_account_health(client: Any, org_id: str, entity: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    eid = str(entity["id"])
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    observations = (
        client.table("entity_observations")
        .select("dimension, label, score, evidence_quote, source_system, source_record_id, observed_at, status, correction")
        .eq("org_id", org_id)
        .eq("entity_id", eid)
        .gte("observed_at", since)
        .limit(500)
        .execute()
        .data
        or []
    )
    signals = (
        client.table("entity_behavior_signals")
        .select("signal, value, baseline, window_end, evidence_count")
        .eq("org_id", org_id)
        .eq("entity_id", eid)
        .order("window_end", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    work = (
        client.table("work_objects")
        .select("id, title, status")
        .eq("org_id", org_id)
        .eq("business_entity_id", eid)
        .limit(200)
        .execute()
        .data
        or []
    )
    systems = sorted({
        str(r.get("system"))
        for r in client.table("org_business_entity_bindings").select("system").eq("org_id", org_id).eq("entity_id", eid).execute().data
        or []
        if r.get("system")
    })
    return build_account_health(entity, observations, signals, work, systems=systems, now=now)


def list_account_health(client: Any, org_id: str, *, limit: int = 20, now: datetime | None = None) -> dict[str, Any]:
    """Accounts with recent evidence, most at-risk dimensions first. Batched reads."""
    now = now or datetime.now(UTC)
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    observations = (
        client.table("entity_observations")
        .select("entity_id, dimension, label, score, evidence_quote, source_system, source_record_id, observed_at, status, correction")
        .eq("org_id", org_id)
        .gte("observed_at", since)
        .limit(5000)
        .execute()
        .data
        or []
    )
    signals = (
        client.table("entity_behavior_signals")
        .select("entity_id, signal, value, baseline, window_end, evidence_count")
        .eq("org_id", org_id)
        .gte("window_end", (now - timedelta(days=7)).date().isoformat())
        .limit(2000)
        .execute()
        .data
        or []
    )
    ids = sorted({str(r["entity_id"]) for r in observations + signals if r.get("entity_id")})[:500]
    if not ids:
        return {"accounts": [], "generatedAt": now.isoformat()}
    entities = client.table("org_business_entities").select("id, display_name").eq("org_id", org_id).in_("id", ids).execute().data or []
    work = (
        client.table("work_objects")
        .select("id, title, status, business_entity_id")
        .eq("org_id", org_id)
        .in_("business_entity_id", ids)
        .limit(2000)
        .execute()
        .data
        or []
    )
    obs_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sig_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    work_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in observations:
        obs_by[str(r.get("entity_id"))].append(r)
    for r in signals:
        sig_by[str(r.get("entity_id"))].append(r)
    for r in work:
        work_by[str(r.get("business_entity_id"))].append(r)
    accounts = []
    for e in entities:
        eid = str(e["id"])
        h = build_account_health(e, obs_by[eid], sig_by[eid], work_by[eid], now=now)
        accounts.append(
            {
                "entity": h["entity"],
                "statusCounts": h["statusCounts"],
                "atRisk": [d["label"] for d in h["dimensions"] if d["status"] == "at_risk"],
                "watch": [d["label"] for d in h["dimensions"] if d["status"] == "watch"],
            }
        )
    accounts.sort(key=lambda a: (-len(a["atRisk"]), -len(a["watch"]), str(a["entity"]["name"])))
    return {"accounts": accounts[: max(1, min(limit, 100))], "generatedAt": now.isoformat()}
