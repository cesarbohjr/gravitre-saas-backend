"""24h execution-outcome ops summary for Module A stream consumers."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any


def _bucket_key(value: str | None, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def summarize_outcomes_last_24h(client: Any, *, org_id: str) -> dict[str, Any]:
    """Aggregate intelligence_outcome_events for pass/fail by source and connector."""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        rows = (
            client.table("intelligence_outcome_events")
            .select("id,outcome_event,metadata,created_at,workflow_run_id")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []

    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0, "cancel": 0})
    by_connector: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0, "cancel": 0})
    totals = {"pass": 0, "fail": 0, "cancel": 0, "other": 0}

    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source = _bucket_key(meta.get("source"), fallback="unknown")
        connector = _bucket_key(
            meta.get("integration")
            or meta.get("connector")
            or meta.get("vendor")
            or (
                (meta.get("verified_output") or {}).get("integration")
                if isinstance(meta.get("verified_output"), dict)
                else None
            ),
            fallback="unspecified",
        )
        event = str(row.get("outcome_event") or "").lower()
        terminal = str(meta.get("terminal_status") or "").lower()
        if event in {"workflow_failed", "run_failed"} or terminal == "failed":
            bucket = "fail"
        elif event in {"workflow_cancelled", "run_cancelled"} or terminal == "cancelled":
            bucket = "cancel"
        elif event in {"workflow_completed", "run_completed"} or terminal in {
            "completed",
            "partial_success",
        }:
            bucket = "pass"
        else:
            totals["other"] += 1
            continue
        totals[bucket] += 1
        by_source[source][bucket] += 1
        by_connector[connector][bucket] += 1

    def _rate(block: dict[str, int]) -> float | None:
        decided = block["pass"] + block["fail"]
        if decided <= 0:
            return None
        return round(block["pass"] / decided, 4)

    return {
        "window_hours": 24,
        "since": since,
        "totals": totals,
        "pass_rate": _rate(totals),
        "by_source": [
            {
                "source": key,
                **counts,
                "pass_rate": _rate(counts),
            }
            for key, counts in sorted(by_source.items(), key=lambda item: (-(item[1]["fail"] + item[1]["pass"]), item[0]))
        ],
        "by_connector": [
            {
                "connector": key,
                **counts,
                "pass_rate": _rate(counts),
            }
            for key, counts in sorted(
                by_connector.items(),
                key=lambda item: (-(item[1]["fail"] + item[1]["pass"]), item[0]),
            )
        ],
        "event_count": len(rows),
    }
