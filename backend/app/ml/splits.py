"""Phase 6: time-based train/holdout splits.

A random split lets a model learn from the future and be graded on the past,
which flatters it. When every example carries the time its label was observed,
train on the earliest examples and hold out the latest, the way the model will
actually be used. Returns ``None`` when a time split is not possible (missing
or unparseable times, or a side with a single class), so the caller can fall
back and say which split it used.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _ts(value: Any) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def time_split(
    observed_at: list[Any],
    labels: list[int],
    *,
    holdout_fraction: float = 0.2,
) -> tuple[list[int], list[int], str] | None:
    """(train indices, holdout indices, holdout start) ordered by time, or None."""
    if not observed_at or len(observed_at) != len(labels):
        return None
    stamps = [_ts(v) for v in observed_at]
    if any(s is None for s in stamps):
        return None
    order = sorted(range(len(stamps)), key=lambda i: stamps[i])  # type: ignore[arg-type,return-value]
    n_hold = max(1, round(len(order) * holdout_fraction))
    train, hold = order[:-n_hold], order[-n_hold:]
    if len({labels[i] for i in train}) < 2 or len({labels[i] for i in hold}) < 2:
        return None
    return train, hold, stamps[hold[0]].isoformat()  # type: ignore[union-attr]
