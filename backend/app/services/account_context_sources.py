"""Gravitre 3.0 Plus account intelligence as ranked context-engine sources.

When a turn names a customer account the org has filed, this module turns what
the platform knows about that account into ``ContextSource`` rows, so the active
cross-source engine ranks, deduplicates and budgets them with everything else
instead of a separate card being appended outside the budget.

Each input has its own flag (all default off) and its own source type, and each
says plainly what kind of statement it is:

* ``customer_quote`` (CONTEXT_ENGINE_OBSERVATIONS_V1): the customer's own words,
  with the system, record id, date and the classifier's confidence. Text only;
  voice never reads quotes aloud.
* ``account_interpretation`` (CONTEXT_ENGINE_OBSERVATIONS_V1): trend directions
  computed by Gravitre from classified messages. Never a customer statement.
* ``account_measurement`` (CONTEXT_ENGINE_ACCOUNT_SIGNALS_V1): behaviour signals
  counted from messages (measured facts), and the rule-based health status
  derived from them (labelled as Gravitre's rule, not a fact or a prediction).
* ``work_state`` (CONTEXT_ENGINE_WORK_STATE_V1): work linked to the account, with
  its recorded status worded so a proposal is never read as a completed action.

Governance, read at turn time and failing closed: observations count only when
the org still allows customer context for that vendor and a live (not deleted,
not revoked) connector of that vendor remains. Measured signals carry no vendor,
so they need customer context on and at least one permitted, live customer
channel. Quotes pass through the retrieved-content guard
when RETRIEVED_CONTENT_GUARD_ENABLED is on. Every read is org-scoped.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.context_prioritization_engine import ContextSource
from app.services.entity_observations import CUSTOMER_FACING_SOURCES
from app.services.source_governance import customer_context_allowed

logger = get_logger(__name__)

OBSERVATIONS_FLAG = "context_engine_observations_v1"
SIGNALS_FLAG = "context_engine_account_signals_v1"
WORK_STATE_FLAG = "context_engine_work_state_v1"

OBSERVATION_WINDOW_DAYS = 90
TREND_WINDOW_DAYS = 30
MAX_QUOTES_PER_ACCOUNT = 3
MAX_QUOTE_CHARS = 240
MAX_WORK_ITEMS = 6
_DEAD_CONNECTOR_STATUSES = frozenset({"revoked", "disconnected", "deleted", "inactive", "disabled"})
_NEUTRAL_LABELS = frozenset({"neutral", "none"})

# How a recorded work status may be described. A proposal is not work, and a
# recorded "completed" is a status in Gravitre, not an independently checked outcome.
WORK_STATUS_WORDING: dict[str, str] = {
    "proposed": "PROPOSED by Gravitre; not approved and not started",
    "identified": "identified; not started",
    "planned": "planned; not started",
    "in_progress": "in progress; not finished",
    "awaiting_approval": "waiting for approval; not executed",
    "blocked": "blocked; not finished",
    "completed": "recorded as completed in Gravitre (a recorded status, not an independently verified outcome)",
    "failed": "failed; not completed",
}


def _on(settings: Any, name: str) -> bool:
    return getattr(settings, name, False) is True


def observations_on(settings: Any) -> bool:
    return _on(settings, OBSERVATIONS_FLAG)


def any_enabled(settings: Any) -> bool:
    return any(_on(settings, f) for f in (OBSERVATIONS_FLAG, SIGNALS_FLAG, WORK_STATE_FLAG))


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _live_vendors(client: Any, org_id: str) -> set[str]:
    """Vendors with a connector that is not deleted or revoked. Raises on read failure."""
    from app.connectors.provider_revoke import canonical_vendor

    res = (
        client.table("connectors")
        .select("type, vendor, status, deleted_at")
        .eq("org_id", org_id)
        .execute()
    )
    out: set[str] = set()
    for row in res.data or []:
        if not isinstance(row, dict) or row.get("deleted_at"):
            continue
        if str(row.get("status") or "").strip().lower() in _DEAD_CONNECTOR_STATUSES:
            continue
        for key in ("vendor", "type"):
            v = canonical_vendor(row.get(key))
            if v:
                out.add(v)
    return out


def governed_observations(
    rows: list[dict[str, Any]], *, policy: dict[str, Any] | None, live_vendors: set[str]
) -> tuple[list[dict[str, Any]], int]:
    """Observations the org still permits and whose source is still connected."""
    from app.connectors.provider_revoke import canonical_vendor

    kept: list[dict[str, Any]] = []
    for r in rows:
        if r.get("status") == "retracted":
            continue
        system = canonical_vendor(r.get("source_system"))
        if not customer_context_allowed(policy, system) or system not in live_vendors:
            continue
        kept.append(r)
    return kept, len(rows) - len(kept)


def _effective(row: dict[str, Any]) -> tuple[str, float]:
    corr = row.get("correction") if isinstance(row.get("correction"), dict) else {}
    return str(corr.get("label") or row.get("label") or ""), float(corr.get("score", row.get("score") or 0.0))


def _read_observations(
    client: Any, org_id: str, entity_id: str, now: datetime, settings: Any = None
) -> list[dict[str, Any]]:
    from app.services.memory_source_liveness import observation_columns

    since = (now - timedelta(days=OBSERVATION_WINDOW_DAYS)).isoformat()
    res = (
        client.table("entity_observations")
        .select(
            observation_columns(
                "id, dimension, label, score, confidence, evidence_quote, source_system, "
                "source_record_id, observed_at, status, correction",
                settings,
            )
        )
        .eq("org_id", org_id)
        .eq("entity_id", entity_id)
        .gte("observed_at", since)
        .order("observed_at", desc=True)
        .limit(200)
        .execute()
    )
    return [r for r in res.data or [] if isinstance(r, dict)]


def _read_signals(client: Any, org_id: str, entity_id: str) -> list[dict[str, Any]]:
    res = (
        client.table("entity_behavior_signals")
        .select("signal, value, baseline, window_end, evidence_count")
        .eq("org_id", org_id)
        .eq("entity_id", entity_id)
        .order("window_end", desc=True)
        .limit(10)
        .execute()
    )
    return [r for r in res.data or [] if isinstance(r, dict)]


def _read_work(client: Any, org_id: str, entity_id: str) -> list[dict[str, Any]]:
    res = (
        client.table("work_objects")
        .select("id, title, status, goal_id, updated_at")
        .eq("org_id", org_id)
        .eq("business_entity_id", entity_id)
        .order("updated_at", desc=True)
        .limit(50)
        .execute()
    )
    return [r for r in res.data or [] if isinstance(r, dict)]


def _goal_titles(client: Any, org_id: str, goal_ids: list[str]) -> dict[str, str]:
    if not goal_ids:
        return {}
    res = client.table("goals").select("id, title").eq("org_id", org_id).in_("id", goal_ids).execute()
    return {str(g.get("id")): str(g.get("title") or "") for g in res.data or [] if isinstance(g, dict)}


def quote_sources(
    name: str, entity_id: str, rows: list[dict[str, Any]], *, guard: bool
) -> tuple[list[ContextSource], int]:
    """The customer's own words, newest first, one source per distinct quote."""
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in sorted(rows, key=lambda r: str(r.get("observed_at")), reverse=True):
        label, _ = _effective(r)
        quote = " ".join(str(r.get("evidence_quote") or "").split())
        if label in _NEUTRAL_LABELS or not quote or quote.lower() in seen:
            continue
        seen.add(quote.lower())
        picked.append({**r, "_quote": quote[:MAX_QUOTE_CHARS], "_label": label})
    excluded = 0
    if guard and picked:
        from app.services.ingested_content_guard import guard_retrieved_chunks

        kept, reasons = guard_retrieved_chunks([{"content": p["_quote"], "row": p} for p in picked])
        picked = [k["row"] for k in kept]
        excluded = len(reasons)
    out: list[ContextSource] = []
    for p in picked[:MAX_QUOTES_PER_ACCOUNT]:
        system = str(p.get("source_system") or "")
        record = str(p.get("source_record_id") or "")
        try:
            confidence = f"{float(p.get('confidence')):.2f}"
        except (TypeError, ValueError):
            confidence = "unknown"
        content = (
            f'{name} customer, in their own words ({system} record {record}, {_date(p.get("observed_at"))}): '
            f'"{p["_quote"]}"\n'
            f"Gravitre's classifier read this as {p.get('dimension')} = {p['_label']} "
            f"(confidence {confidence}); the classification is Gravitre's, the words are the customer's."
        )
        out.append(
            ContextSource(
                source_id=f"customer_quote:{system}:{record}:{p.get('dimension')}",
                source_type="customer_quote",
                label=f"{name}: customer message ({system}, {_date(p.get('observed_at'))})",
                score=0.0,
                content=content,
                metadata={
                    "source_identity": f"{system}:{record}",
                    "entity_id": entity_id,
                    "observed_at": p.get("observed_at"),
                    "citation": f"{system}:{record}",
                    "statement_kind": "customer_words",
                },
            )
        )
    return out, excluded


def interpretation_source(
    name: str, entity_id: str, rows: list[dict[str, Any]], *, now: datetime
) -> ContextSource | None:
    """Trend directions with enough evidence, clearly marked as Gravitre's reading."""
    from app.services.entity_observations import DIMENSIONS, trend

    scored = []
    for r in rows:
        label, score = _effective(r)
        scored.append({**r, "label": label, "score": score, "correction": None})
    lines = []
    for dim in DIMENSIONS:
        t = trend(scored, dimension=dim, now=now, window_days=TREND_WINDOW_DAYS)
        if t["direction"] == "insufficient_evidence":
            continue
        lines.append(
            f"- {dim.replace('_', ' ')}: {t['direction']} over {TREND_WINDOW_DAYS} days "
            f"({t['observations']} classified observations from {t['sources']} messages)"
        )
    if not lines:
        return None
    latest = max((str(r.get("observed_at") or "") for r in rows), default="")
    content = (
        f"{name}: Gravitre's interpretation of recent customer messages. These trends are computed "
        "by Gravitre's classifier; they are not statements the customer made and not verified facts.\n"
        + "\n".join(lines)
    )
    return ContextSource(
        source_id=f"account_interpretation:{entity_id}",
        source_type="account_interpretation",
        label=f"{name}: Gravitre's interpretation of customer messages",
        score=0.0,
        content=content,
        metadata={
            "source_identity": f"account_interpretation:{entity_id}",
            "entity_id": entity_id,
            "observed_at": latest or None,
            "statement_kind": "interpretation",
        },
    )


def measurement_source(
    entity: dict[str, Any],
    observations: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    *,
    now: datetime,
) -> ContextSource | None:
    """Counted behaviour signals (facts) and the health rules applied to them (Gravitre's rule)."""
    from app.services.account_health import build_account_health

    name = str(entity.get("display_name") or "")
    eid = str(entity.get("id") or "")
    latest: dict[str, dict[str, Any]] = {}
    for s in sorted(signals, key=lambda s: str(s.get("window_end")), reverse=True):
        latest.setdefault(str(s.get("signal")), s)
    measured = []
    for key, s in latest.items():
        try:
            value = float(s.get("value") or 0)
        except (TypeError, ValueError):
            continue
        as_of = _date(s.get("window_end"))
        if key == "contact_volume_change":
            measured.append(f"- customer message volume, last 14 days: {value:.1f}x the usual rate (as of {as_of})")
        elif key == "contact_gap_days":
            measured.append(f"- days since the last customer message: {round(value)} (as of {as_of})")
        else:
            measured.append(f"- {key}: {value:g} (as of {as_of})")
    health = build_account_health(entity, observations, signals, [], now=now)
    statuses = [
        f"- {d['label']}: {d['status']}"
        for d in health.get("dimensions") or []
        if d.get("status") not in {"unknown", None} and d.get("key") != "open_work"
    ]
    if not measured and not statuses:
        return None
    parts = [f"{name}: account measurements."]
    if measured:
        parts.append("Measured from message counts (facts, rule beh-v1):")
        parts.extend(measured)
    if statuses:
        parts.append(
            "Health status from Gravitre's written rules applied to those measurements and to "
            "classified messages (Gravitre's assessment, not a customer statement and not a prediction):"
        )
        parts.extend(statuses)
    window_end = max((str(s.get("window_end") or "") for s in signals), default="")
    return ContextSource(
        source_id=f"account_measurement:{eid}",
        source_type="account_measurement",
        label=f"{name}: measured account signals and rule-based health",
        score=0.0,
        content="\n".join(parts),
        metadata={
            "source_identity": f"account_measurement:{eid}",
            "entity_id": eid,
            "observed_at": window_end or None,
            "statement_kind": "measurement",
        },
    )


def work_source(
    name: str, entity_id: str, work: list[dict[str, Any]], goals: dict[str, str]
) -> ContextSource | None:
    """Linked work with its recorded status, worded so proposals never read as done."""
    lines = []
    for w in work:
        status = str(w.get("status") or "").strip().lower()
        wording = WORK_STATUS_WORDING.get(status)
        if wording is None:
            continue
        goal = goals.get(str(w.get("goal_id") or ""))
        goal_part = f" (goal: {goal})" if goal else ""
        lines.append(f'- "{str(w.get("title") or "untitled")[:120]}"{goal_part}: {wording}, updated {_date(w.get("updated_at"))}')
        if len(lines) >= MAX_WORK_ITEMS:
            break
    if not lines:
        return None
    latest = max((str(w.get("updated_at") or "") for w in work), default="")
    return ContextSource(
        source_id=f"work_state:{entity_id}",
        source_type="work_state",
        label=f"{name}: work linked to this account",
        score=0.0,
        content=(
            f"{name}: work linked to this account in Gravitre, with each item's recorded status. "
            "Only items recorded as completed were done; describe proposed, planned or pending items "
            "as not yet done.\n" + "\n".join(lines)
        ),
        metadata={
            "source_identity": f"work_state:{entity_id}",
            "entity_id": entity_id,
            "last_updated": latest or None,
            "statement_kind": "recorded_status",
        },
    )


def build_account_context_sources(
    client: Any,
    org_id: str,
    message: str,
    *,
    spoken: bool,
    settings: Any,
    now: datetime | None = None,
) -> tuple[list[ContextSource], dict[str, Any]]:
    """Return (sources, meta) for accounts named in the message. Never raises."""
    if not any_enabled(settings) or client is None or not org_id:
        return [], {"skipped": "disabled"}
    started = time.perf_counter()
    now = now or datetime.now(UTC)
    meta: dict[str, Any] = {"inputs": [f for f in (OBSERVATIONS_FLAG, SIGNALS_FLAG, WORK_STATE_FLAG) if _on(settings, f)]}
    try:
        from app.services.entity_context_card import _org_entities, match_accounts

        accounts = match_accounts(message, _org_entities(client, org_id))
        if not accounts:
            meta["skipped"] = "no_account_named"
            return [], meta
        policy: dict[str, Any] | None = None
        live: set[str] = set()
        governance_ok = True
        try:
            from app.services.source_governance import load_source_governance

            policy = load_source_governance(client, org_id)
            live = _live_vendors(client, org_id)
        except Exception as exc:  # noqa: BLE001
            governance_ok = False
            logger.warning("account_context_governance_unreadable org_id=%s error=%s", org_id, type(exc).__name__)
        customer_context_on = bool(governance_ok and (policy or {}).get("customerContext", {}).get("enabled"))
        # Signals are counted across customer channels and carry no vendor, so
        # they are shown only while at least one permitted customer channel is live.
        signal_sources_live = any(
            customer_context_allowed(policy, v) for v in live & CUSTOMER_FACING_SOURCES
        )
        guard = False
        if not spoken:
            from app.services.ingested_content_guard import guard_enabled

            guard = guard_enabled(settings)
        sources: list[ContextSource] = []
        withheld = 0
        quote_guard_excluded = 0
        from app.services.memory_source_liveness import (
            drop_observations_from_revoked_sources,
        )

        for acc in accounts:
            eid = str(acc.get("id") or "")
            name = str(acc.get("display_name") or "")
            observations: list[dict[str, Any]] = []
            read: list[dict[str, Any]] = []
            if customer_context_on and (_on(settings, OBSERVATIONS_FLAG) or _on(settings, SIGNALS_FLAG)):
                read = _read_observations(client, org_id, eid, now, settings)
                # Per connector (MEMORY_SOURCE_LINEAGE_ENABLED): a revoked connection is
                # excluded even while another connection of the same vendor is live.
                raw, _ = drop_observations_from_revoked_sources(
                    client, org_id, read, [], settings=settings, entity_id=eid
                )
                observations, dropped = governed_observations(raw, policy=policy, live_vendors=live)
                withheld += dropped + (len(read) - len(raw))
            if _on(settings, OBSERVATIONS_FLAG) and observations:
                interp = interpretation_source(name, eid, observations, now=now)
                if interp is not None:
                    sources.append(interp)
                if not spoken:
                    quotes, excluded = quote_sources(name, eid, observations, guard=guard)
                    sources.extend(quotes)
                    quote_guard_excluded += excluded
            if _on(settings, SIGNALS_FLAG) and customer_context_on and signal_sources_live:
                _, signals = drop_observations_from_revoked_sources(
                    client, org_id, read, _read_signals(client, org_id, eid), settings=settings, entity_id=eid
                )
                measured = measurement_source(acc, observations, signals, now=now)
                if measured is not None:
                    sources.append(measured)
            if _on(settings, WORK_STATE_FLAG):
                work = _read_work(client, org_id, eid)
                goal_ids = sorted({str(w.get("goal_id")) for w in work if w.get("goal_id")})
                ws = work_source(name, eid, work, _goal_titles(client, org_id, goal_ids))
                if ws is not None:
                    sources.append(ws)
        meta.update(
            {
                "accounts": [str(a.get("id")) for a in accounts],
                "sourceCount": len(sources),
                "byType": {t: sum(1 for s in sources if s.source_type == t) for t in sorted({s.source_type for s in sources})},
                "withheldByGovernance": withheld,
                "customerContextEnabled": customer_context_on,
                "spoken": spoken,
                "ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        if not governance_ok:
            meta["governanceUnreadable"] = True
        if quote_guard_excluded:
            meta["quoteInjectionExcluded"] = quote_guard_excluded
        return sources, meta
    except Exception as exc:  # noqa: BLE001
        logger.warning("account_context_sources_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return [], {**meta, "skipped": "error"}
