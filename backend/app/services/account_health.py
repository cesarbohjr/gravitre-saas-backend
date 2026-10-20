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


# The direction of change that drives each observation dimension's status. The
# account health page, the recommendation feed and the chat/voice account card
# all read trends through ``read_observations`` so the three cannot drift apart.
OBSERVATION_DIMENSIONS: tuple[str, ...] = (
    "sentiment",
    "churn_risk_language",
    "support_friction",
    "urgency",
    "expansion_interest",
)
NOTABLE_DIRECTION: dict[str, str] = {
    "sentiment": "falling",
    "churn_risk_language": "rising",
    "support_friction": "rising",
    "urgency": "rising",
    "expansion_interest": "rising",
}
_NEUTRAL_LABELS = frozenset({"neutral", "none"})


def quotable_observations(rows: list[dict[str, Any]], dimension: str | None = None) -> list[dict[str, Any]]:
    """Observations worth quoting, newest first: not retracted, not a neutral label."""
    return [
        r
        for r in sorted(rows, key=lambda r: str(r.get("observed_at")), reverse=True)
        if (dimension is None or r.get("dimension") == dimension)
        and r.get("status") != "retracted"
        and r.get("label") not in _NEUTRAL_LABELS
    ]


def quote_line(row: dict[str, Any]) -> str:
    return f'"{row.get("evidence_quote")}" ({row.get("source_system")}, {str(row.get("observed_at"))[:10]})'


def observation_status(key: str, direction: str, mean: float | None) -> str:
    """The written rule for one observation dimension (see DEFINITIONS)."""
    if direction == "insufficient_evidence":
        return "unknown"
    if key == "sentiment":
        return "at_risk" if direction == "falling" else ("watch" if (mean or 0) < 0 else "healthy")
    if key in {"churn_risk_language", "support_friction"}:
        return "at_risk" if direction == "rising" else ("watch" if (mean or 0) > MEAN_WATCH else "healthy")
    if key == "urgency":
        return "watch" if direction == "rising" else "healthy"
    return "healthy"


def read_observations(
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    dimensions: tuple[str, ...] | list[str] = OBSERVATION_DIMENSIONS,
    window_days: int = WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """One reading per observation dimension: trend, status and quotable evidence.

    ``notable`` is true when the trend moved in the direction that drives the
    dimension's status (falling sentiment; rising churn language, friction,
    urgency or expansion interest). ``opportunity`` marks rising expansion.
    """
    out = []
    for key in dimensions:
        t = trend(rows, dimension=key, now=now, window_days=window_days)
        direction = t["direction"]
        notable = direction == NOTABLE_DIRECTION.get(key)
        out.append(
            {
                "key": key,
                "trend": t,
                "direction": direction,
                "status": observation_status(key, direction, t.get("latest_mean")),
                "notable": notable,
                "opportunity": notable and key == "expansion_interest",
                "quotes": quotable_observations(rows, key),
            }
        )
    return out


def _observation_dims(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    out = []
    for r in read_observations(rows, now=now):
        key, t, direction = r["key"], r["trend"], r["direction"]
        coverage = {"observations": t["observations"], "messages": t["sources"], "window_days": WINDOW_DAYS}
        quotes = [quote_line(q) for q in r["quotes"]]
        if direction == "insufficient_evidence":
            out.append(_dim(key, "unknown", None, quotes, coverage, "Not enough observations yet."))
            continue
        value = {"direction": direction, "recent_mean": t.get("latest_mean"), "change": t.get("delta")}
        out.append(_dim(key, r["status"], value, quotes, coverage, "Opportunity." if r["opportunity"] else ""))
    return out


def latest_signals(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The newest row per behaviour signal."""
    latest: dict[str, dict[str, Any]] = {}
    for s in sorted(signals, key=lambda s: str(s.get("window_end")), reverse=True):
        latest.setdefault(str(s.get("signal")), s)
    return latest


def signal_dims(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = latest_signals(signals)
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
    dims = _observation_dims(observations, now) + signal_dims(signals) + [_work_dim(work)]
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


def load_account_health(
    client: Any, org_id: str, entity: dict[str, Any], *, now: datetime | None = None, settings: Any = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    eid = str(entity["id"])
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    from app.services.memory_source_liveness import (
        drop_observations_from_revoked_sources,
        observation_columns,
    )

    observations = (
        client.table("entity_observations")
        .select(
            observation_columns(
                "dimension, label, score, evidence_quote, source_system, source_record_id, observed_at, status, correction",
                settings,
            )
        )
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
    observations, signals = drop_observations_from_revoked_sources(
        client, org_id, observations, signals, settings=settings, entity_id=eid
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


def load_health_batch(
    client: Any, org_id: str, *, now: datetime | None = None, settings: Any = None
) -> list[dict[str, Any]]:
    """Full health for every account with recent evidence, in a few batched reads."""
    from app.services.memory_source_liveness import (
        drop_observations_from_revoked_sources,
        observation_columns,
    )

    now = now or datetime.now(UTC)
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    observations = (
        client.table("entity_observations")
        .select(
            observation_columns(
                "entity_id, dimension, label, score, evidence_quote, source_system, source_record_id, observed_at, status, correction",
                settings,
            )
        )
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
    observations, signals = drop_observations_from_revoked_sources(
        client, org_id, observations, signals, settings=settings
    )
    ids = sorted({str(r["entity_id"]) for r in observations + signals if r.get("entity_id")})[:500]
    if not ids:
        return []
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
    return [
        build_account_health(e, obs_by[str(e["id"])], sig_by[str(e["id"])], work_by[str(e["id"])], now=now)
        for e in entities
    ]


def list_account_health(client: Any, org_id: str, *, limit: int = 20, now: datetime | None = None) -> dict[str, Any]:
    """Accounts with recent evidence, most at-risk dimensions first. Batched reads."""
    now = now or datetime.now(UTC)
    accounts = []
    for h in load_health_batch(client, org_id, now=now):
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
