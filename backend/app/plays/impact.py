"""Aggregate verified Play impact without converting execution into business success."""
from __future__ import annotations
from typing import Any
from app.plays.outcomes import list_play_business_results

VERIFIED_SUCCESS = "VERIFIED SUCCESS"
VERIFIED_FAILURE = "VERIFIED FAILURE"

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}


def range_since(range_key: str | None) -> str | None:
    from datetime import datetime, timedelta, timezone

    days = RANGE_DAYS.get(str(range_key or "").strip().lower())
    if not days:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def counts_in_total(meta: dict[str, Any]) -> bool:
    """Assisted verified results (a later Play on an already-claimed record) never add to totals."""
    return meta.get("counted_in_total") is not False


def _aggregation(metric: str) -> str:
    try:
        from app.outcome_packs.registry import metric_definition

        return str((metric_definition(metric) or {}).get("aggregation") or "count")
    except Exception:
        return "count"


def _metric_value(metric: str, meta: dict[str, Any], row: dict[str, Any]) -> float | None:
    """Value one verified row contributes: the measured value for averages, else the delta."""
    raw = row.get("after_value") if _aggregation(metric) == "avg" else meta.get("delta_value")
    return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None


def _finalise(bucket: dict[str, Any]) -> dict[str, Any]:
    samples = bucket.pop("_samples", 0)
    if bucket.pop("_avg", False) and samples:
        bucket["value"] = bucket["value"] / samples
    return bucket


def play_impact_summary(
    client: Any,
    org_id: str,
    *,
    limit: int = 1000,
    range_key: str | None = None,
) -> dict[str, Any]:
    rows = list_play_business_results(
        client, org_id, limit=limit, since=range_since(range_key), max_limit=5000
    )
    by_play: dict[str, dict[str, Any]] = {}
    totals: dict[str, dict[str, Any]] = {}
    verified_count = 0
    pending_count = 0

    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        key = str(meta.get("play_key") or "").strip()
        if not key:
            continue
        status = str(meta.get("verification_state") or "").strip().upper()
        item = by_play.setdefault(key, {
            "playKey": key,
            "verifiedSuccessCount": 0,
            "verifiedFailureCount": 0,
            "pendingVerificationCount": 0,
            "actionedCount": 0,
            "verifiedMetrics": {},
            "latestResultAt": None,
        })
        created = row.get("created_at")
        if created and (not item["latestResultAt"] or str(created) > str(item["latestResultAt"])):
            item["latestResultAt"] = created

        if status == VERIFIED_SUCCESS and not counts_in_total(meta):
            item.setdefault("assistedCount", 0)
            item["assistedCount"] += 1
        elif status == VERIFIED_SUCCESS:
            verified_count += 1
            item["verifiedSuccessCount"] += 1
            metric = str(meta.get("metric_key") or "").strip()
            value = _metric_value(metric, meta, row) if metric else None
            unit = str(meta.get("unit") or "").strip()
            currency = str(meta.get("currency") or "").strip()
            if value is not None:
                metric_key = f"{metric}|{unit}|{currency}"
                is_avg = _aggregation(metric) == "avg"
                for bucket in (item["verifiedMetrics"], totals):
                    current = bucket.setdefault(metric_key, {
                        "metricKey": metric, "value": 0.0, "unit": unit or None, "currency": currency or None,
                        "_avg": is_avg, "_samples": 0,
                    })
                    current["value"] += value
                    current["_samples"] += 1
        elif status == VERIFIED_FAILURE:
            item["verifiedFailureCount"] += 1
        elif status == "PENDING VERIFICATION":
            pending_count += 1
            item["pendingVerificationCount"] += 1
        elif status == "ACTIONED":
            item["actionedCount"] += 1

    for item in by_play.values():
        item["verifiedMetrics"] = [_finalise(m) for m in item["verifiedMetrics"].values()]

    total_metrics = [_finalise(m) for m in totals.values()]

    return {
        "range": range_key,
        "plays": list(by_play.values()),
        "verifiedResultCount": verified_count,
        "pendingVerificationCount": pending_count,
        "verifiedMetrics": total_metrics,
        "truthRule": (
            "Only source-of-record VERIFIED SUCCESS results contribute to verified impact totals; "
            "assisted results on an already-counted record are shown but not added."
        ),
    }
