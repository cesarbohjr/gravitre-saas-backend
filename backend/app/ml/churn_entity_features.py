"""Optional entity features for the churn model (CHURN_ENTITY_FEATURES_ENABLED).

Two pieces, both read-only:

1. ``map_churn_customers_to_entities``: a churn subject is a bare
   ``customer_id`` string (``agent_action_outcomes.target_entity_id``). It is
   mapped to an ``org_business_entities`` row only through an accepted
   ``org_business_entity_bindings`` row whose ``resource_id`` equals it, and
   only when every such binding points at the same entity. No binding, or
   bindings to two entities, stays unmapped. Nothing is matched by name.

2. ``entity_features_as_of``: per mapped entity, observation aggregates
   (``entity_observations``: count, mean score and trend delta per dimension)
   and the latest rule-based behaviour signals (``entity_behavior_signals``),
   computed strictly from evidence observed *before* an as-of time. Training
   rows use ``as_of = label time - LABEL_GAP_DAYS`` so the words that announce
   a cancellation cannot stand in for the label. Too little evidence is
   ``None`` (missing), never 0.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.entity_observations import DIMENSIONS, trend

logger = get_logger(__name__)

# Features describe the account this long before its churn label was recorded.
LABEL_GAP_DAYS = 30
# Observation look-back, ending at the as-of time.
OBSERVATION_WINDOW_DAYS = 90
# A behaviour signal older than this at the as-of time is treated as missing.
SIGNAL_RECENCY_DAYS = 14

OBS_DIMENSIONS: tuple[str, ...] = tuple(DIMENSIONS)
SIGNALS: tuple[str, ...] = ("contact_volume_change", "contact_gap_days")

ENTITY_FEATURE_KEYS: tuple[str, ...] = (
    ("obs_message_count",)
    + tuple(f"obs_{d}_{agg}" for d in OBS_DIMENSIONS for agg in ("count", "mean", "delta"))
    + tuple(f"sig_{s}" for s in SIGNALS)
)

MAPPED = "mapped"
UNMAPPED = "unmapped"
AMBIGUOUS = "ambiguous"

_CHUNK = 200
_ROW_LIMIT = 20000


def _ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        out = value
    else:
        try:
            out = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def _chunks(items: list[str]) -> list[list[str]]:
    return [items[i : i + _CHUNK] for i in range(0, len(items), _CHUNK)]


def map_churn_customers_to_entities(
    client: Any, org_id: str, customer_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """``{customer_id: {"status", "entity_id"}}`` from existing bindings only.

    ``mapped`` needs at least one binding with ``resource_id == customer_id``
    and all of them on one entity; two or more entities is ``ambiguous``; none
    is ``unmapped``. A failed lookup leaves everything unmapped.
    """
    ids = sorted({str(c) for c in customer_ids if c not in (None, "")})
    out: dict[str, dict[str, Any]] = {c: {"status": UNMAPPED, "entity_id": None} for c in ids}
    if not ids:
        return out
    hits: dict[str, set[str]] = defaultdict(set)
    try:
        for chunk in _chunks(ids):
            rows = (
                client.table("org_business_entity_bindings")
                .select("entity_id, system, resource_type, resource_id")
                .eq("org_id", org_id)
                .in_("resource_id", chunk)
                .execute()
                .data
                or []
            )
            for row in rows:
                rid = str(row.get("resource_id") or "")
                eid = str(row.get("entity_id") or "")
                if rid in out and eid:
                    hits[rid].add(eid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("churn_entity_mapping_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return out
    for cid, entities in hits.items():
        if len(entities) == 1:
            out[cid] = {"status": MAPPED, "entity_id": next(iter(entities))}
        else:
            out[cid] = {"status": AMBIGUOUS, "entity_id": None, "candidates": len(entities)}
    return out


def _as_of_view(row: dict[str, Any], as_of: datetime) -> dict[str, Any] | None:
    """The observation as it stood at ``as_of``, or None if it was not yet observed.

    A human correction or retraction only counts if it was made before as_of;
    otherwise the extractor's original judgement is what was knowable then.
    """
    observed = _ts(row.get("observed_at"))
    if observed is None or observed >= as_of:
        return None
    view = dict(row)
    corrected_at = _ts(row.get("corrected_at"))
    if row.get("status") in {"corrected", "retracted"} and corrected_at is not None and corrected_at < as_of:
        return view
    view["status"] = "active"
    view["correction"] = None
    return view


def entity_features_as_of(
    observations: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    *,
    as_of: datetime,
    window_days: int = OBSERVATION_WINDOW_DAYS,
) -> dict[str, float | None]:
    """Aggregates over ``[as_of - window_days, as_of)``. Missing evidence is None."""
    feats: dict[str, float | None] = {k: None for k in ENTITY_FEATURE_KEYS}
    start = as_of - timedelta(days=window_days)
    view = [v for v in (_as_of_view(r, as_of) for r in observations) if v is not None]
    view = [v for v in view if _ts(v.get("observed_at")) > start]  # type: ignore[operator]
    live = [v for v in view if v.get("status") != "retracted"]
    if live:
        # Coverage exists: per-dimension counts are real counts (0 is a true 0).
        feats["obs_message_count"] = float(
            len({f"{v.get('source_system')}:{v.get('source_record_id')}" for v in live})
        )
        for dim in OBS_DIMENSIONS:
            t = trend(view, dimension=dim, now=as_of, window_days=window_days)
            feats[f"obs_{dim}_count"] = float(t["observations"])
            if t["direction"] == "insufficient_evidence":
                continue  # mean and delta stay missing
            scores = [
                float((v.get("correction") or {}).get("score", v.get("score", 0.0)))
                for v in live
                if v.get("dimension") == dim
            ]
            feats[f"obs_{dim}_mean"] = round(sum(scores) / len(scores), 4) if scores else None
            feats[f"obs_{dim}_delta"] = float(t["delta"]) if t.get("delta") is not None else None
    as_of_day = as_of.date()
    earliest = (as_of - timedelta(days=SIGNAL_RECENCY_DAYS)).date()
    latest: dict[str, tuple[Any, float]] = {}
    for s in signals:
        name = str(s.get("signal") or "")
        if name not in SIGNALS:
            continue
        end = _ts(s.get("window_end"))
        if end is None:
            continue
        day = end.date()
        # window_end is a date; only windows that closed before the as-of day count.
        if not (earliest <= day < as_of_day):
            continue
        try:
            value = float(s.get("value"))
        except (TypeError, ValueError):
            continue
        if name not in latest or day > latest[name][0]:
            latest[name] = (day, value)
    for name, (_day, value) in latest.items():
        feats[f"sig_{name}"] = value
    return feats


def load_entity_features(
    client: Any,
    org_id: str,
    subjects: list[tuple[str, datetime]],
    *,
    window_days: int = OBSERVATION_WINDOW_DAYS,
) -> tuple[list[dict[str, float | None]], dict[str, Any]]:
    """Entity features for each ``(customer_id, as_of)``, in order, plus coverage.

    Batched reads bounded by the earliest window start and the latest as-of;
    each subject is then cut to its own as-of in Python.
    """
    empty = {k: None for k in ENTITY_FEATURE_KEYS}
    mapping = map_churn_customers_to_entities(client, org_id, [c for c, _ in subjects])
    coverage = {
        "subjects": len(subjects),
        MAPPED: sum(1 for c, _ in subjects if mapping.get(str(c), {}).get("status") == MAPPED),
        UNMAPPED: sum(1 for c, _ in subjects if mapping.get(str(c), {}).get("status", UNMAPPED) == UNMAPPED),
        AMBIGUOUS: sum(1 for c, _ in subjects if mapping.get(str(c), {}).get("status") == AMBIGUOUS),
    }
    entity_ids = sorted({str(m["entity_id"]) for m in mapping.values() if m.get("status") == MAPPED})
    if not entity_ids or not subjects:
        return [dict(empty) for _ in subjects], coverage
    lo = min(a for _, a in subjects)
    hi = max(a for _, a in subjects)
    obs_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sig_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    try:
        for chunk in _chunks(entity_ids):
            for r in (
                client.table("entity_observations")
                .select(
                    "entity_id, dimension, score, source_system, source_record_id, "
                    "observed_at, status, correction, corrected_at"
                )
                .eq("org_id", org_id)
                .in_("entity_id", chunk)
                .gte("observed_at", (lo - timedelta(days=window_days)).isoformat())
                .lt("observed_at", hi.isoformat())
                .limit(_ROW_LIMIT)
                .execute()
                .data
                or []
            ):
                obs_by[str(r.get("entity_id"))].append(r)
            for r in (
                client.table("entity_behavior_signals")
                .select("entity_id, signal, value, window_end")
                .eq("org_id", org_id)
                .in_("entity_id", chunk)
                .gte("window_end", (lo - timedelta(days=SIGNAL_RECENCY_DAYS)).date().isoformat())
                .lt("window_end", hi.date().isoformat())
                .limit(_ROW_LIMIT)
                .execute()
                .data
                or []
            ):
                sig_by[str(r.get("entity_id"))].append(r)
    except Exception as exc:  # noqa: BLE001
        logger.warning("churn_entity_features_failed org_id=%s error=%s", org_id, type(exc).__name__)
        coverage["read_failed"] = True
        return [dict(empty) for _ in subjects], coverage
    out: list[dict[str, float | None]] = []
    for cid, as_of in subjects:
        m = mapping.get(str(cid)) or {}
        if m.get("status") != MAPPED:
            out.append(dict(empty))
            continue
        eid = str(m["entity_id"])
        out.append(entity_features_as_of(obs_by[eid], sig_by[eid], as_of=as_of, window_days=window_days))
    return out, coverage


def training_as_of(measured_at: Any, *, gap_days: int = LABEL_GAP_DAYS) -> datetime | None:
    """As-of time for a labelled row: the label time minus the gap."""
    ts = _ts(measured_at)
    return ts - timedelta(days=gap_days) if ts is not None else None


def join_features(crm: dict[str, Any], entity: dict[str, float | None]) -> dict[str, Any]:
    """The five CRM features with the optional entity features alongside (None = missing)."""
    return {**dict(crm), **entity}
