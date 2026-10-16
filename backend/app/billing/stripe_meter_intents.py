"""Stable Stripe meter intent identity and billable delta calculations.

These helpers are side-effect free. A database outbox must persist the resulting
intent before any external Stripe call. Do not use batch membership as an
idempotency key: appending a row changes the batch identifier on retry.
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Iterable


def meter_event_identifier(
    *,
    org_id: str,
    environment: str,
    metric_type: str,
    period_start: date,
    source_event_id: str,
) -> str:
    """Use the immutable source event, not the changing set of pending rows."""
    values = (org_id, environment, metric_type, period_start.isoformat(), source_event_id)
    if any(not value for value in values):
        raise ValueError("Meter event identity requires every scope component")
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def new_overage_delta(*, total_before: int, total_after: int, included: int) -> int:
    """Charge only usage which *newly* crossed the included allowance."""
    if min(total_before, total_after, included) < 0 or total_after < total_before:
        raise ValueError("Invalid cumulative usage or allowance")
    return max(total_after - included, 0) - max(total_before - included, 0)


def ordered_event_deltas(events: Iterable[tuple[str, int]], *, included: int) -> list[tuple[str, int]]:
    """Assign deterministic overage quantities to immutable ordered source rows.

    Production callers must read ordering and allowance under a database lock.
    This calculation alone is not an outbox/concurrency guard.
    """
    if included < 0:
        raise ValueError("Included quantity must be nonnegative")
    cumulative = 0
    deltas: list[tuple[str, int]] = []
    seen: set[str] = set()
    for event_id, quantity in events:
        if not event_id or event_id in seen or quantity < 0:
            raise ValueError("Invalid or duplicate source event")
        seen.add(event_id)
        next_total = cumulative + quantity
        deltas.append((event_id, new_overage_delta(
            total_before=cumulative, total_after=next_total, included=included,
        )))
        cumulative = next_total
    return deltas
