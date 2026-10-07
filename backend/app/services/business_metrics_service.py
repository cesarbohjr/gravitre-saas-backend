"""Business metric values computed only from source-of-record verified Play results.

Definitions come from the canonical catalog (Outcome Pack metrics + legacy
platform defaults, with ``org_metric_definitions`` overrides winning). Values
come only from counted VERIFIED SUCCESS rows on the Play outcome ledger. No
verified evidence means ``value: null`` with a reason, never ``0``.
"""
from __future__ import annotations

from typing import Any

from app.plays.impact import counts_in_total, range_since
from app.plays.outcomes import list_play_business_results

TRUTH_RULE = (
    "Values come only from results verified by re-reading the source of record. "
    "Missing evidence is shown as unknown, never as zero."
)

DEPARTMENTS = [
    {"id": "growth", "label": "Growth"},
    {"id": "marketing", "label": "Marketing"},
    {"id": "sales", "label": "Sales"},
    {"id": "customer_success", "label": "Customer Success"},
    {"id": "support", "label": "Support"},
    {"id": "msp", "label": "MSP Service Desk"},
    {"id": "operations", "label": "Operations"},
    {"id": "finance", "label": "Finance"},
    {"id": "executive", "label": "Executive"},
]


def _definitions(client: Any, org_id: str) -> dict[str, dict[str, Any]]:
    from app.services.cognitive_metrics import list_metric_definitions, list_platform_defaults

    out: dict[str, dict[str, Any]] = {}
    for row in list_platform_defaults():
        key = str(row.get("metric_key") or "").lower()
        out[key] = {**row, "owner": "platform"}
    for row in list_metric_definitions(client, org_id, limit=500):
        key = str(row.get("metric_key") or "").lower()
        base = out.get(key, {"metric_key": key, "kind": "business", "aggregation": "count", "unit": "count"})
        out[key] = {
            **base,
            "label": row.get("label") or base.get("label") or key,
            "formula": row.get("formula") or base.get("formula"),
            "source_system": row.get("source_system") or base.get("source_system"),
            "owner": "org",
        }
    return out


def _public_definition(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metricKey": row.get("metric_key"),
        "label": row.get("label") or row.get("metric_key"),
        "description": row.get("description") or row.get("formula") or "",
        "department": row.get("department"),
        "departments": list(row.get("departments") or []),
        "kind": row.get("kind") or "business",
        "unit": row.get("unit") or "count",
        "direction": "down" if row.get("direction") == "decrease" else "up",
        "sourceSystem": row.get("source_system"),
        "sourceRecordType": row.get("source_record_type"),
        "verificationMethod": row.get("verification_recipe"),
        "aggregation": row.get("aggregation") or "count",
        "numerator": row.get("numerator"),
        "denominator": row.get("denominator"),
        "owner": row.get("owner") or "platform",
        "packs": list(row.get("packs") or []),
        "verifiable": bool(row.get("verification_recipe")) or row.get("aggregation") == "ratio",
    }


def business_metric_catalog(client: Any, org_id: str) -> dict[str, Any]:
    defs = _definitions(client, org_id)
    return {
        "metrics": [_public_definition(row) for _, row in sorted(defs.items())],
        "departments": DEPARTMENTS,
    }


def _verified_rows(client: Any, org_id: str, range_key: str | None) -> list[dict[str, Any]]:
    rows = list_play_business_results(client, org_id, limit=5000, since=range_since(range_key), max_limit=5000)
    out = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(meta.get("verification_state") or "").upper() == "VERIFIED SUCCESS":
            out.append(row)
    return out


def _aggregate(definition: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counted verified rows for one non-ratio metric."""
    counted = [r for r in rows if counts_in_total(r.get("metadata") or {})]
    assisted = len(rows) - len(counted)
    latest = max((str(r.get("measured_at") or r.get("created_at") or "") for r in counted), default=None) or None
    base = {"verifiedResultCount": len(counted), "assistedResultCount": assisted, "latestVerifiedAt": latest}
    if not counted:
        reason = (
            "No source-of-record verification is declared for this metric yet."
            if not definition.get("verification_recipe")
            else "No Play result for this metric has been verified in the source system yet."
        )
        return {**base, "value": None, "currency": None, "status": "no_verified_evidence", "reason": reason}
    aggregation = definition.get("aggregation") or "count"
    currencies = {str((r.get("metadata") or {}).get("currency") or "") for r in counted} - {""}
    if definition.get("unit") == "currency" and len(currencies) > 1:
        return {**base, "value": None, "currency": None, "status": "insufficient_data",
                "reason": f"Verified results use more than one currency ({', '.join(sorted(currencies))})."}
    currency = next(iter(currencies), None)
    if aggregation == "avg":
        values = [float(r["after_value"]) for r in counted if isinstance(r.get("after_value"), (int, float))]
        if not values:
            return {**base, "value": None, "currency": currency, "status": "insufficient_data",
                    "reason": "Verified results carry no measured value."}
        return {**base, "value": sum(values) / len(values), "currency": currency, "status": "verified", "reason": None}
    deltas = [(r.get("metadata") or {}).get("delta_value") for r in counted]
    numeric = [float(d) for d in deltas if isinstance(d, (int, float))]
    return {**base, "value": sum(numeric), "currency": currency, "status": "verified", "reason": None}


def compute_business_metrics(
    client: Any,
    org_id: str,
    *,
    range_key: str | None = "30d",
    metric_keys: list[str] | None = None,
) -> dict[str, Any]:
    defs = _definitions(client, org_id)
    rows = _verified_rows(client, org_id, range_key)
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str((row.get("metadata") or {}).get("metric_key") or "").lower()
        by_metric.setdefault(key, []).append(row)

    wanted = [k.strip().lower() for k in (metric_keys or sorted(defs)) if k and k.strip()]
    cache: dict[str, dict[str, Any]] = {}

    def value_for(key: str) -> dict[str, Any]:
        if key in cache:
            return cache[key]
        definition = defs.get(key)
        if definition is None:
            cache[key] = {"metricKey": key, "value": None, "unit": None, "currency": None, "status": "not_defined",
                          "reason": "This metric is not defined for your workspace.", "verifiedResultCount": 0,
                          "assistedResultCount": 0, "latestVerifiedAt": None}
            return cache[key]
        unit = definition.get("unit") or "count"
        if definition.get("aggregation") == "ratio":
            num = value_for(str(definition.get("numerator") or ""))
            den = value_for(str(definition.get("denominator") or ""))
            if num["value"] is None or den["value"] in (None, 0):
                result = {"value": None, "currency": None, "status": "no_verified_evidence" if den["value"] is None else "insufficient_data",
                          "reason": f"Needs verified {definition.get('numerator')} and {definition.get('denominator')}.",
                          "verifiedResultCount": num["verifiedResultCount"] + den["verifiedResultCount"],
                          "assistedResultCount": 0, "latestVerifiedAt": max(filter(None, [num["latestVerifiedAt"], den["latestVerifiedAt"]]), default=None)}
            else:
                ratio = float(num["value"]) / float(den["value"])
                result = {"value": ratio * 100 if unit == "percent" else ratio, "currency": None, "status": "verified", "reason": None,
                          "verifiedResultCount": num["verifiedResultCount"] + den["verifiedResultCount"],
                          "assistedResultCount": num["assistedResultCount"] + den["assistedResultCount"],
                          "latestVerifiedAt": max(filter(None, [num["latestVerifiedAt"], den["latestVerifiedAt"]]), default=None)}
        else:
            result = _aggregate(definition, by_metric.get(key, []))
        cache[key] = {"metricKey": key, "unit": unit, **result}
        return cache[key]

    return {
        "range": range_key,
        "metrics": [value_for(key) for key in wanted],
        "truthRule": TRUTH_RULE,
    }


def business_metric_evidence(
    client: Any,
    org_id: str,
    metric_key: str,
    *,
    range_key: str | None = "30d",
    limit: int = 100,
) -> dict[str, Any]:
    key = str(metric_key or "").strip().lower()
    summary = compute_business_metrics(client, org_id, range_key=range_key, metric_keys=[key])["metrics"][0]
    rows = list_play_business_results(client, org_id, limit=5000, since=range_since(range_key), max_limit=5000)
    contributions = []
    exceptions = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(meta.get("metric_key") or "").lower() != key:
            continue
        state = str(meta.get("verification_state") or "").upper()
        play_key = str(meta.get("play_key") or "")
        if state == "VERIFIED SUCCESS":
            contributions.append(
                {
                    "outcomeId": row.get("id"),
                    "playKey": play_key,
                    "value": meta.get("delta_value"),
                    "resultValue": row.get("after_value"),
                    "baselineValue": row.get("before_value"),
                    "unit": meta.get("unit"),
                    "currency": meta.get("currency"),
                    "attributionType": meta.get("attribution_type"),
                    "attributionWeight": meta.get("attribution_weight"),
                    "countedInTotal": counts_in_total(meta),
                    "sourceRecords": list(meta.get("source_records") or []),
                    "verificationMethod": meta.get("verification_method"),
                    "verifiedAt": row.get("measured_at") or row.get("created_at"),
                    "evidenceHref": f"/plays/{play_key}/results/{row.get('id')}",
                }
            )
        elif state in {"VERIFIED FAILURE", "INCONCLUSIVE"}:
            exceptions.append(
                {
                    "outcomeId": row.get("id"),
                    "kind": "verified_failure" if state == "VERIFIED FAILURE" else "inconclusive",
                    "message": meta.get("inconclusive_reason")
                    or ("The source record shows this result did not happen." if state == "VERIFIED FAILURE" else "No decisive evidence."),
                    "playKey": play_key,
                }
            )
    return {
        **summary,
        "range": range_key,
        "contributions": contributions[: max(1, min(int(limit), 500))],
        "exceptions": exceptions[:100],
    }
