"""3.0-A latency baseline aggregation from runtime.turn_latency.critical_path audits."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def percentile(sorted_vals: list[int], p: float) -> int | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = int(round((len(sorted_vals) - 1) * p))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, idx))]


def stats_ms(values: list[int]) -> dict[str, Any]:
    s = sorted(values)
    return {
        "sample_count": len(s),
        "p50_ms": percentile(s, 0.50),
        "p95_ms": percentile(s, 0.95),
        "max_ms": s[-1] if s else None,
    }


def parse_audit_metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def aggregate_critical_path_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce critical-path audit rows to p50/p95 baselines by stage."""
    totals: list[int] = []
    dominant_deltas: list[int] = []
    by_dominant_stage: dict[str, list[int]] = defaultdict(list)
    by_stage_delta: dict[str, list[int]] = defaultdict(list)

    for row in rows:
        meta = parse_audit_metadata(row)
        total_ms = meta.get("total_ms")
        dominant_ms = meta.get("dominant_ms")
        dominant_stage = str(meta.get("dominant_stage") or "").strip()

        if isinstance(total_ms, (int, float)):
            totals.append(int(total_ms))
        if isinstance(dominant_ms, (int, float)):
            dominant_deltas.append(int(dominant_ms))
            if dominant_stage:
                by_dominant_stage[dominant_stage].append(int(dominant_ms))

        stages = meta.get("stages")
        if isinstance(stages, list):
            for stage_row in stages:
                if not isinstance(stage_row, dict):
                    continue
                stage = str(stage_row.get("stage") or "").strip()
                delta_ms = stage_row.get("delta_ms")
                if stage and isinstance(delta_ms, (int, float)):
                    by_stage_delta[stage].append(int(delta_ms))

    dominant_stage_summary = {
        stage: {**stats_ms(values), "win_count": len(values)}
        for stage, values in sorted(by_dominant_stage.items())
    }
    stage_delta_summary = {
        stage: stats_ms(values) for stage, values in sorted(by_stage_delta.items())
    }

    return {
        "sample_count": len(rows),
        "turn_total_ms": stats_ms(totals),
        "dominant_delta_ms": stats_ms(dominant_deltas),
        "by_dominant_stage": dominant_stage_summary,
        "by_stage_delta_ms": stage_delta_summary,
    }


def aggregate_slo_metric_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[int] = []
    for row in rows:
        meta = parse_audit_metadata(row)
        raw = meta.get("ms")
        if isinstance(raw, (int, float)):
            values.append(int(raw))
    return stats_ms(values)


def split_cohorts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    text: list[dict[str, Any]] = []
    voice: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for row in rows:
        meta = parse_audit_metadata(row)
        spoken = meta.get("spoken_mode")
        if spoken is True:
            voice.append(row)
        elif spoken is False:
            text.append(row)
        else:
            unknown.append(row)
    return {"all": rows, "text": text, "voice": voice, "unknown_spoken_mode": unknown}
