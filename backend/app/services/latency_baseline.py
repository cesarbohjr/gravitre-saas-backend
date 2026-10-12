"""Phase 2D: chat and voice latency baseline, and a regression gate against it.

Reads the per-turn critical-path traces both surfaces already write to
``audit_events`` (action ``runtime.turn_latency.critical_path``):

* text turns (``record_critical_path``): ``total_ms`` is the turn's last
  checkpoint, the time to the composed answer;
* voice turns (``record_voice_turn_critical_path``, ``voice_transport`` set):
  ``stage_durations_ms.speech_end_to_playback_ms``, falling back to
  ``speech_end_to_server_audio_ms`` when the browser did not report playback.

A baseline is a JSON object of p50/p95 per surface. ``compare`` fails a surface
whose p50 or p95 grew by more than the allowed percentage, but only when both
sides have enough samples to say so.
"""
from __future__ import annotations

import math
from typing import Any

MIN_SAMPLES = {"p50": 20, "p95": 50}
VOICE_TOTAL_KEYS = ("speech_end_to_playback_ms", "speech_end_to_server_audio_ms")


def _pct(sorted_values: list[float], pct: float) -> float:
    rank = max(1, math.ceil(pct / 100.0 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def turn_total_ms(payload: dict[str, Any]) -> tuple[str, float | None]:
    """Return (surface, total ms) for one trace payload."""
    if payload.get("voice_transport"):
        durations = payload.get("stage_durations_ms")
        durations = durations if isinstance(durations, dict) else {}
        for key in VOICE_TOTAL_KEYS:
            value = durations.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return "voice", float(value)
        return "voice", None
    value = payload.get("total_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return "text", float(value)
    return "text", None


def summarize(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: dict[str, list[float]] = {"text": [], "voice": []}
    for p in payloads or []:
        if not isinstance(p, dict):
            continue
        surface, total = turn_total_ms(p)
        if total is not None:
            values[surface].append(total)
    out: dict[str, dict[str, Any]] = {}
    for surface, vals in values.items():
        vals.sort()
        n = len(vals)
        out[surface] = {
            "n": n,
            "p50": round(_pct(vals, 50)) if n >= MIN_SAMPLES["p50"] else None,
            "p95": round(_pct(vals, 95)) if n >= MIN_SAMPLES["p95"] else None,
        }
    return out


def compare(
    current: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    *,
    max_regression_pct: float = 10.0,
) -> list[dict[str, Any]]:
    """One verdict row per surface and percentile: ok, regressed or insufficient."""
    rows: list[dict[str, Any]] = []
    for surface in ("text", "voice"):
        cur = current.get(surface) or {}
        base = baseline.get(surface) or {}
        for pct in ("p50", "p95"):
            c, b = cur.get(pct), base.get(pct)
            if c is None or b is None or not b:
                rows.append({"surface": surface, "pct": pct, "verdict": "insufficient", "baseline": b, "current": c})
                continue
            change = (float(c) - float(b)) / float(b) * 100.0
            rows.append(
                {
                    "surface": surface,
                    "pct": pct,
                    "baseline": b,
                    "current": c,
                    "change_pct": round(change, 1),
                    "verdict": "regressed" if change > max_regression_pct else "ok",
                }
            )
    return rows
