"""Runtime evidence that source lifecycle is enforced in this process.

The ingestion interlock (``ingestion_interlock``) used to trust configuration
flags. Configuration says what should happen; this module records what is
happening, so new ingestion is allowed only while all of these hold here:

* the domain event relay task was started in this process and has not exited;
* the relay completed a tick recently (heartbeat), so ``source.disconnected``
  events are being claimed;
* the source purge handler is registered for ``source.disconnected``;
* a database probe, run by the relay off the event loop, recently confirmed that
  ``purge_connector_derived_data`` exists and is callable (dry run, no write),
  that the outbox is readable, that no ``source.disconnected`` event is
  dead-lettered and that none has waited longer than ``PURGE_MAX_LAG_SECONDS``.

Everything fails closed: no evidence, stale evidence or an error while reading
it is "not ready". Readiness is per process: a process that does not run the
relay (for example ``scripts/ingest_worker.py``) is never ready.

The hot path (``runtime_lifecycle_blockers``) reads in-memory state only. The
database probe runs every ``DB_PROBE_EVERY_S`` inside the relay loop.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

DB_PROBE_EVERY_S = 60
# A probe older than this no longer counts (three missed probes).
DB_PROBE_MAX_AGE_S = 3 * DB_PROBE_EVERY_S
# Floor for the relay heartbeat window, whatever the configured interval.
MIN_HEARTBEAT_WINDOW_S = 60
# A source.disconnected event still pending after this long means purges are not keeping up.
PURGE_MAX_LAG_SECONDS = 3600

# Raised by purge_connector_derived_data for null arguments: proves the function
# exists and runs, without touching any row or writing a receipt.
PURGE_RPC_SENTINEL = "org, connector and disconnected_at are required"


def required_handlers() -> tuple[tuple[str, str], ...]:
    from app.services.domain_events import EVENT_SOURCE_DISCONNECTED
    from app.services.source_lifecycle import PURGE_HANDLER_NAME

    return ((EVENT_SOURCE_DISCONNECTED, PURGE_HANDLER_NAME),)


@dataclass
class _RelayState:
    task: Any = None
    interval_s: int = 0
    lease_s: int = 0
    started_at: float | None = None
    last_ok_tick_at: float | None = None
    last_tick_error: str | None = None
    consecutive_failures: int = 0
    db_probe: dict[str, Any] | None = None
    db_probe_at: float | None = None


_lock = threading.Lock()
_state = _RelayState()


def _now() -> float:
    return time.monotonic()


def reset_lifecycle_runtime_for_tests() -> None:
    global _state
    with _lock:
        _state = _RelayState()


def relay_started(task: Any, *, interval_s: int, lease_s: int = 0) -> None:
    with _lock:
        _state.task = task
        _state.interval_s = max(0, int(interval_s or 0))
        _state.lease_s = max(0, int(lease_s or 0))
        _state.started_at = _now()
        _state.last_ok_tick_at = None
        _state.last_tick_error = None
        _state.consecutive_failures = 0
        _state.db_probe = None
        _state.db_probe_at = None


def relay_stopped() -> None:
    with _lock:
        _state.task = None
        _state.last_ok_tick_at = None
        _state.db_probe = None
        _state.db_probe_at = None


def record_relay_tick(*, ok: bool, error: str | None = None) -> None:
    with _lock:
        if ok:
            _state.last_ok_tick_at = _now()
            _state.last_tick_error = None
            _state.consecutive_failures = 0
        else:
            _state.last_tick_error = (error or "unknown")[:300]
            _state.consecutive_failures += 1


def record_db_probe(result: dict[str, Any]) -> None:
    with _lock:
        _state.db_probe = dict(result)
        _state.db_probe_at = _now()


def heartbeat_window_s() -> int:
    return max(MIN_HEARTBEAT_WINDOW_S, 4 * _state.interval_s, _state.interval_s + _state.lease_s)


def _error_text(exc: BaseException) -> str:
    parts = [str(getattr(exc, attr, "") or "") for attr in ("message", "details", "hint")]
    parts.append(str(exc))
    return " ".join(p for p in parts if p)


def probe_lifecycle_database(client: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Read-only checks of the purge machinery. Synchronous; run in a thread.

    Returns ``{"ok": bool, "blockers": [...], "checks": {...}}``. Never raises.
    """
    from app.services.domain_events import EVENT_SOURCE_DISCONNECTED, OUTBOX_TABLE

    now = now or datetime.now(UTC)
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    # 1) Purge RPC exists and executes. Null arguments make it raise before any read or
    #    write; dry run is requested as well in case that guard is ever removed.
    try:
        client.rpc(
            "purge_connector_derived_data",
            {
                "p_org_id": None,
                "p_connector_id": None,
                "p_vendor": None,
                "p_disconnected_at": None,
                "p_dry_run": True,
                "p_event_id": None,
            },
        ).execute()
        checks["purge_rpc"] = "unexpected_success"
        blockers.append("purge_rpc_unverified")
    except Exception as exc:  # noqa: BLE001
        if PURGE_RPC_SENTINEL in _error_text(exc):
            checks["purge_rpc"] = "present"
        else:
            code = str(getattr(exc, "code", "") or type(exc).__name__)
            checks["purge_rpc"] = f"missing_or_failing:{code}"
            blockers.append(f"purge_rpc_unavailable:{code}")

    # 2) Outbox readable, no dead-lettered purge, no purge waiting too long.
    try:
        dead = (
            client.table(OUTBOX_TABLE)
            .select("id")
            .eq("event_type", EVENT_SOURCE_DISCONNECTED)
            .eq("status", "dead")
            .limit(1)
            .execute()
        )
        checks["purge_dead_letters"] = len(dead.data or [])
        if dead.data:
            blockers.append("purge_dead_lettered")
        cutoff = (now - timedelta(seconds=PURGE_MAX_LAG_SECONDS)).isoformat()
        lagging = (
            client.table(OUTBOX_TABLE)
            .select("id")
            .eq("event_type", EVENT_SOURCE_DISCONNECTED)
            .in_("status", ["pending", "processing"])
            .lt("created_at", cutoff)
            .limit(1)
            .execute()
        )
        checks["purge_lagging"] = len(lagging.data or [])
        if lagging.data:
            blockers.append("purge_lagging")
    except Exception as exc:  # noqa: BLE001
        checks["outbox"] = f"unreadable:{type(exc).__name__}"
        blockers.append("outbox_unreadable")

    return {"ok": not blockers, "blockers": blockers, "checks": checks}


def runtime_lifecycle_blockers() -> list[str]:
    """Why this process cannot prove lifecycle enforcement right now ([] = ready)."""
    try:
        return _blockers()
    except Exception as exc:  # noqa: BLE001
        logger.warning("lifecycle_runtime_check_failed error=%s", type(exc).__name__)
        return ["runtime_state_unknown"]


def _blockers() -> list[str]:
    from app.services.domain_events import handlers_for

    out: list[str] = []
    now = _now()
    with _lock:
        task = _state.task
        last_ok = _state.last_ok_tick_at
        probe = _state.db_probe
        probe_at = _state.db_probe_at
        window = heartbeat_window_s()

    if task is None:
        out.append("relay_not_running")
    elif bool(getattr(task, "done", lambda: True)()):
        out.append("relay_task_exited")
    if last_ok is None:
        out.append("relay_no_successful_tick")
    elif now - last_ok > window:
        out.append(f"relay_heartbeat_stale:{int(now - last_ok)}s")

    for event_type, name in required_handlers():
        if not any(r.name == name for r in handlers_for(event_type)):
            out.append(f"handler_missing:{event_type}:{name}")

    if probe is None or probe_at is None:
        out.append("db_probe_missing")
    elif now - probe_at > DB_PROBE_MAX_AGE_S:
        out.append(f"db_probe_stale:{int(now - probe_at)}s")
    elif probe.get("ok") is not True:
        out.extend(str(b) for b in (probe.get("blockers") or ["db_probe_failed"]))
    return out


def runtime_lifecycle_status() -> dict[str, Any]:
    """Snapshot for the readiness report (no I/O)."""
    blockers = runtime_lifecycle_blockers()
    now = _now()
    with _lock:
        s = _state
        return {
            "ready": not blockers,
            "blockers": blockers,
            "relay_task": None if s.task is None else ("exited" if s.task.done() else "running"),
            "heartbeat_age_s": None if s.last_ok_tick_at is None else int(now - s.last_ok_tick_at),
            "heartbeat_window_s": heartbeat_window_s(),
            "last_tick_error": s.last_tick_error,
            "consecutive_tick_failures": s.consecutive_failures,
            "db_probe_age_s": None if s.db_probe_at is None else int(now - s.db_probe_at),
            "db_probe": s.db_probe,
        }
