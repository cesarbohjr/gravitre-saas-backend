"""Durable domain events (Phase 2A): transactional outbox + relay.

Producers
---------
Critical events are written by Postgres triggers in the same transaction as the
business change (``supabase/migrations/20261011220000_domain_event_outbox.sql``):

* ``execution.outcome_finalized``: a ``workflow_runs`` row enters a terminal status.
* ``source.disconnected``: a connector is soft-deleted, or a connected row is
  hard-deleted (organisation deletion cascade).

Application code never has to remember to emit those, and a rolled-back change
never leaves an event behind. ``enqueue_domain_event`` exists for best-effort
events that have no single owning row; it is idempotent on
``(event_type, idempotency_key)``.

Relay
-----
``DomainEventRelay.run_once`` claims due events with ``claim_domain_events``
(``FOR UPDATE SKIP LOCKED`` plus a lease, so several replicas can run it),
runs every registered handler for the event type, then completes or fails the
event. Delivery is at least once: a handler may see the same ``event_id`` again
after a crash or lease expiry, so handlers must be idempotent (key on
``event_id`` or on the aggregate). Handlers that already succeeded are recorded
on the row and skipped on retry. Failed events back off exponentially and are
dead-lettered after ``max_attempts``; dead events are never pruned.

The relay is off unless ``DOMAIN_EVENT_RELAY_ENABLED`` is true.
"""
from __future__ import annotations

import os
import socket
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

EVENT_EXECUTION_OUTCOME_FINALIZED = "execution.outcome_finalized"
EVENT_SOURCE_DISCONNECTED = "source.disconnected"

OUTBOX_TABLE = "domain_event_outbox"

# Retry backoff: base * 2^(attempt-1), capped. attempt 1 -> 15s, 5 -> 4m, 8+ -> 1h.
RETRY_BASE_SECONDS = 15
RETRY_MAX_SECONDS = 3600

Handler = Callable[[Any, dict[str, Any]], None]


@dataclass(frozen=True)
class _Registration:
    name: str
    fn: Handler


_handlers: dict[str, list[_Registration]] = {}


def register_domain_event_handler(event_type: str, name: str, fn: Handler) -> None:
    """Subscribe ``fn(client, event_row)`` to ``event_type`` under a stable ``name``.

    ``name`` is persisted in ``delivered_handlers``; renaming a handler makes
    the relay treat it as new and run it again for retried events.
    """
    regs = _handlers.setdefault(event_type, [])
    if any(r.name == name for r in regs):
        raise ValueError(f"domain event handler {name!r} already registered for {event_type!r}")
    regs.append(_Registration(name=name, fn=fn))


def handlers_for(event_type: str) -> list[_Registration]:
    return list(_handlers.get(event_type, []))


def handled_event_types() -> list[str]:
    """Event types with at least one registered handler; the relay claims only these."""
    return sorted(t for t, regs in _handlers.items() if regs)


def reset_domain_event_handlers_for_tests() -> None:
    _handlers.clear()


def retry_delay_seconds(attempts: int) -> int:
    exponent = max(0, int(attempts or 1) - 1)
    return int(min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** min(exponent, 20))))


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def enqueue_domain_event(
    client: Any,
    *,
    org_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Best-effort enqueue for events with no owning row change.

    Idempotent: a second call with the same ``(event_type, idempotency_key)`` is
    ignored. Returns False (and logs) instead of raising, because a caller that
    needs the event to be atomic with its change must use a trigger instead.
    """
    row = {
        "org_id": str(org_id),
        "event_type": event_type,
        "aggregate_type": aggregate_type,
        "aggregate_id": str(aggregate_id),
        "idempotency_key": str(idempotency_key),
        "payload": payload or {},
        "criticality": "best_effort",
    }
    try:
        client.table(OUTBOX_TABLE).upsert(
            row,
            on_conflict="event_type,idempotency_key",
            ignore_duplicates=True,
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "domain_event_enqueue_failed event_type=%s aggregate_id=%s error=%s",
            event_type,
            aggregate_id,
            exc,
        )
        return False


@dataclass
class RelayTickResult:
    claimed: int = 0
    delivered: int = 0
    retried: int = 0
    dead: int = 0
    lease_lost: int = 0
    released: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claimed": self.claimed,
            "delivered": self.delivered,
            "retried": self.retried,
            "dead": self.dead,
            "lease_lost": self.lease_lost,
            "released": self.released,
            "errors": self.errors[:5],
        }


class DomainEventRelay:
    def __init__(
        self,
        client: Any,
        *,
        worker_id: str | None = None,
        batch_size: int = 50,
        lease_seconds: int = 120,
    ) -> None:
        self._client = client
        self.worker_id = worker_id or default_worker_id()
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds

    def _claim(self) -> list[dict[str, Any]]:
        # Only types with a registered handler. An event whose handler is off
        # (e.g. OUTCOME_LEARNING_HANDLER_ENABLED=false) stays pending, attempts
        # untouched, instead of being marked delivered with nothing run.
        event_types = handled_event_types()
        if not event_types:
            return []
        res = self._client.rpc(
            "claim_domain_events",
            {
                "p_worker": self.worker_id,
                "p_limit": self.batch_size,
                "p_lease_seconds": self.lease_seconds,
                "p_event_types": event_types,
            },
        ).execute()
        return [r for r in (res.data or []) if isinstance(r, dict)]

    def _release(self, event: dict[str, Any]) -> bool:
        res = self._client.rpc(
            "release_domain_event",
            {"p_id": event.get("id"), "p_worker": self.worker_id},
        ).execute()
        return res.data is True

    def _dispatch(self, event: dict[str, Any]) -> tuple[list[str], str | None]:
        """Run handlers not yet delivered. Returns (delivered handler names, first error)."""
        done = [str(n) for n in (event.get("delivered_handlers") or [])]
        error: str | None = None
        for reg in handlers_for(str(event.get("event_type") or "")):
            if reg.name in done:
                continue
            try:
                reg.fn(self._client, event)
                done.append(reg.name)
            except Exception as exc:  # noqa: BLE001
                error = f"{reg.name}: {type(exc).__name__}: {exc}"
                logger.warning(
                    "domain_event_handler_failed event_id=%s event_type=%s handler=%s attempt=%s error=%s",
                    event.get("event_id"),
                    event.get("event_type"),
                    reg.name,
                    event.get("attempts"),
                    exc,
                )
                # Later handlers still run; each is retried independently.
        return done, error

    def run_once(self) -> RelayTickResult:
        result = RelayTickResult()
        events = self._claim()
        result.claimed = len(events)
        for event in events:
            event_pk = event.get("id")
            if not handlers_for(str(event.get("event_type") or "")):
                # Claimed but nothing would run (a handler was unregistered, or an
                # older claim function ignored the type filter). Never complete it.
                try:
                    if self._release(event):
                        result.released += 1
                    else:
                        result.lease_lost += 1
                except Exception as exc:  # noqa: BLE001
                    # The lease expires and the event returns to pending on its own.
                    result.errors.append(f"release: {exc}")
                    logger.warning(
                        "domain_event_release_failed event_id=%s error=%s", event.get("event_id"), exc
                    )
                continue
            done, error = self._dispatch(event)
            try:
                if error is None:
                    ok = self._client.rpc(
                        "complete_domain_event",
                        {"p_id": event_pk, "p_worker": self.worker_id, "p_delivered_handlers": done},
                    ).execute()
                    if ok.data is True:
                        result.delivered += 1
                    else:
                        result.lease_lost += 1
                        logger.warning(
                            "domain_event_lease_lost event_id=%s worker=%s",
                            event.get("event_id"),
                            self.worker_id,
                        )
                    continue
                res = self._client.rpc(
                    "fail_domain_event",
                    {
                        "p_id": event_pk,
                        "p_worker": self.worker_id,
                        "p_error": error,
                        "p_delivered_handlers": done,
                        "p_retry_seconds": retry_delay_seconds(int(event.get("attempts") or 1)),
                    },
                ).execute()
                new_status = res.data
                result.errors.append(error)
                if new_status == "dead":
                    result.dead += 1
                    logger.error(
                        "domain_event_dead_lettered event_id=%s event_type=%s attempts=%s error=%s",
                        event.get("event_id"),
                        event.get("event_type"),
                        event.get("attempts"),
                        error,
                    )
                elif new_status == "pending":
                    result.retried += 1
                else:
                    result.lease_lost += 1
            except Exception as exc:  # noqa: BLE001
                # The lease expires and another tick (or replica) reclaims the event.
                result.errors.append(f"settle: {exc}")
                logger.warning(
                    "domain_event_settle_failed event_id=%s error=%s", event.get("event_id"), exc
                )
        return result


def domain_event_outbox_stats(client: Any) -> dict[str, Any]:
    res = client.rpc("domain_event_outbox_stats", {}).execute()
    return res.data if isinstance(res.data, dict) else {}


def prune_domain_events(client: Any, *, retention_days: int = 14, batch: int = 5000) -> int:
    res = client.rpc(
        "prune_domain_events", {"p_retention_days": retention_days, "p_batch": batch}
    ).execute()
    return int(res.data or 0)
