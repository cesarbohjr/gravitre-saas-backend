"""Phase 3 evaluation harness for the observation extractor.

Each case is a customer message with the expected label per dimension (missing
means "none"/"neutral"). ``evaluate`` runs any extractor over the cases and
reports, per dimension: label accuracy, and precision/recall of the non-neutral
labels (did it flag what it should, and only that). Grounding is enforced by
``validate_extraction``, so every reported observation quotes the message.

The release gate (``passes_gate``) is what a new extractor version must meet
before it may write to production: it is checked against the labelled set in
``tests/eval/fixtures/observations_v1.jsonl`` with ``scripts/eval_observations.py``.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.services.entity_observations import DIMENSIONS, NEUTRAL_LABELS, Observation

GATE = {
    "sentiment": {"accuracy": 0.8},
    "churn_risk_language": {"precision": 0.85, "recall": 0.7},
    "urgency": {"precision": 0.8},
    "expansion_interest": {"precision": 0.8},
    "support_friction": {"precision": 0.8},
}

Extractor = Callable[[str], Awaitable[list[Observation]]]


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _default_label(dim: str) -> str:
    return "neutral" if dim == "sentiment" else "none"


async def evaluate(cases: list[dict[str, Any]], extractor: Extractor) -> dict[str, Any]:
    counts = {d: {"correct": 0, "total": 0, "tp": 0, "fp": 0, "fn": 0} for d in DIMENSIONS}
    misses: list[dict[str, Any]] = []
    for case in cases:
        got = {o.dimension: o.label for o in await extractor(case["text"])}
        expected = case.get("expected") or {}
        for dim in DIMENSIONS:
            want = str(expected.get(dim) or _default_label(dim))
            have = got.get(dim, _default_label(dim))
            c = counts[dim]
            c["total"] += 1
            c["correct"] += int(want == have)
            want_flag, have_flag = want not in NEUTRAL_LABELS, have not in NEUTRAL_LABELS
            c["tp"] += int(want_flag and have_flag)
            c["fp"] += int(have_flag and not want_flag)
            c["fn"] += int(want_flag and not have_flag)
            if want != have:
                misses.append({"id": case.get("id"), "dimension": dim, "expected": want, "got": have})
    metrics: dict[str, dict[str, float | None]] = {}
    for dim, c in counts.items():
        flagged, actual = c["tp"] + c["fp"], c["tp"] + c["fn"]
        metrics[dim] = {
            "accuracy": round(c["correct"] / c["total"], 3) if c["total"] else None,
            "precision": round(c["tp"] / flagged, 3) if flagged else None,
            "recall": round(c["tp"] / actual, 3) if actual else None,
            "support": actual,
        }
    return {"cases": len(cases), "metrics": metrics, "misses": misses}


def passes_gate(report: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for dim, need in GATE.items():
        got = report["metrics"].get(dim, {})
        for metric, threshold in need.items():
            value = got.get(metric)
            if value is None or value < threshold:
                failures.append(f"{dim}.{metric}={value} < {threshold}")
    return not failures, failures
