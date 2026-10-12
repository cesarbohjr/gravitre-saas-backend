"""Phase 5: Play ``required_signals`` checked against this org's own events.

Readiness used to accept a signal when its name appeared in the platform
event taxonomy, so every org looked ready for every signal. With
PLAY_SIGNAL_EVALUATION_ENABLED, a signal counts as available only when the
org has produced it recently:

- outcome-ledger events (``intelligence_outcome_events.outcome_event``),
- workflow run terminal states (``workflow_completed`` / ``workflow_failed``),
- customer observations, as ``observation.<dimension>``.

Observation names count as known only in evaluated mode, so the legacy name check
never treats an observation signal as available without evidence.

A known signal with no recent events reads PARTIAL with the reason, not
MISSING, so a Play can still say what it is waiting for.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

WINDOW_DAYS = 30
# Workflow run terminal status -> signal name. Also published in the platform event
# taxonomy (capabilities.registry.event_taxonomy, "workflow_run_signals").
WORKFLOW_RUN_SIGNALS = {"completed": "workflow_completed", "failed": "workflow_failed"}


def signal_evaluation_enabled(settings: Any) -> bool:
    return getattr(settings, "play_signal_evaluation_enabled", False) is True


def observation_signal_names() -> set[str]:
    from app.services.entity_observations import DIMENSIONS

    return {f"observation.{dim}" for dim in DIMENSIONS}


def evaluated_signal_names() -> set[str]:
    """Signals this module can observe: workflow run signals (also in the platform
    event taxonomy) and observation signals (known only in evaluated mode)."""
    return set(WORKFLOW_RUN_SIGNALS.values()) | observation_signal_names()


def org_observed_signals(client: Any, org_id: str, *, window_days: int = WINDOW_DAYS) -> set[str]:
    """Signals this org produced in the window. Read errors leave a source out."""
    since = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    seen: set[str] = set()
    reads = (
        ("intelligence_outcome_events", "outcome_event", "created_at", lambda v: str(v)),
        ("workflow_runs", "status", "created_at", lambda v: WORKFLOW_RUN_SIGNALS.get(str(v), "")),
        ("entity_observations", "dimension", "observed_at", lambda v: f"observation.{v}"),
    )
    for table, column, ts, to_signal in reads:
        try:
            rows = (
                client.table(table)
                .select(column)
                .eq("org_id", org_id)
                .gte(ts, since)
                .limit(2000)
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("play_signal_evidence_read_failed table=%s error=%s", table, type(exc).__name__)
            continue
        seen.update(s for s in (to_signal(r.get(column)) for r in rows if isinstance(r, dict)) if s)
    return seen
