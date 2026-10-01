"""Aggregate verified Play impact without converting execution into business success."""
from __future__ import annotations
from collections import defaultdict
from typing import Any
from app.plays.outcomes import list_play_business_results

VERIFIED_SUCCESS = "VERIFIED SUCCESS"
VERIFIED_FAILURE = "VERIFIED FAILURE"

def play_impact_summary(client: Any, org_id: str, *, limit: int = 200) -> dict[str, Any]:
    rows = list_play_business_results(client, org_id, limit=limit)
    by_play: dict[str, dict[str, Any]] = {}
    totals = defaultdict(float)
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

        if status == VERIFIED_SUCCESS:
            verified_count += 1
            item["verifiedSuccessCount"] += 1
            metric = str(meta.get("metric_key") or "").strip()
            delta = meta.get("delta_value")
            unit = str(meta.get("unit") or "").strip()
            currency = str(meta.get("currency") or "").strip()
            if metric and isinstance(delta, (int, float)):
                metric_key = f"{metric}|{unit}|{currency}"
                current = item["verifiedMetrics"].setdefault(metric_key, {
                    "metricKey": metric, "value": 0.0, "unit": unit or None, "currency": currency or None
                })
                current["value"] += float(delta)
                totals[metric_key] += float(delta)
        elif status == VERIFIED_FAILURE:
            item["verifiedFailureCount"] += 1
        elif status == "PENDING VERIFICATION":
            pending_count += 1
            item["pendingVerificationCount"] += 1
        elif status == "ACTIONED":
            item["actionedCount"] += 1

    for item in by_play.values():
        item["verifiedMetrics"] = list(item["verifiedMetrics"].values())

    total_metrics = []
    for composite, value in totals.items():
        metric, unit, currency = composite.split("|", 2)
        total_metrics.append({"metricKey": metric, "value": value, "unit": unit or None, "currency": currency or None})

    return {
        "plays": list(by_play.values()),
        "verifiedResultCount": verified_count,
        "pendingVerificationCount": pending_count,
        "verifiedMetrics": total_metrics,
        "truthRule": "Only source-of-record VERIFIED SUCCESS results contribute to verified impact totals.",
    }
