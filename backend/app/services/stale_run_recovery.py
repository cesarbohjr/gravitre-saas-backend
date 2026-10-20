"""Recover workflow runs left in flight by a worker restart or crash.

A run executes inside one worker process. If that process dies, the run stays
``running`` (or ``verifying``) forever: production on 2026-10-13 had 19 runs
``running`` since June to September with no step activity. Users see a run
that never ends, and nothing tells them whether its effects happened.

This sweep never re-executes anything. For each run with no activity for longer
than the threshold:

* a ``running`` step that may have reached a provider (a write tool call, a
  send, a delegated agent) makes the run ``flagged_for_review``: someone must
  check the source system before anything is retried;
* otherwise the run is ``failed`` with an explicit interruption message, since
  no external effect was in flight;
* a run stuck ``verifying`` becomes ``verification_inconclusive`` (the write
  was accepted; the read-back never finished).

Interrupted steps are marked ``failed`` with ``error_code='interrupted'``.
Every transition is compare-and-set on the old status, so concurrent replicas
or a late-finishing worker win over the sweep, and each recovery is audited.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

INTERRUPTED = "interrupted"
_PAGE = 200


@dataclass
class RecoveryDecision:
    run_id: str
    org_id: str
    from_status: str
    to_status: str
    reason: str
    interrupted_steps: list[str] = field(default_factory=list)
    write_in_flight: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "org_id": self.org_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "interrupted_steps": list(self.interrupted_steps),
            "write_in_flight": self.write_in_flight,
        }


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _last_activity(run: dict[str, Any], steps: list[dict[str, Any]]) -> datetime | None:
    stamps = [_ts(run.get("created_at"))]
    for s in steps:
        stamps.extend(_ts(s.get(k)) for k in ("created_at", "started_at", "completed_at"))
    stamps = [t for t in stamps if t]
    return max(stamps) if stamps else None


def _step_may_have_external_effect(step: dict[str, Any]) -> bool:
    from app.services.outcome_verification import step_action, step_is_consequential

    try:
        return bool(step_is_consequential(step.get("step_type"), step_action(step)))
    except Exception:  # noqa: BLE001  (unknown means assume it may have)
        return True


def decide(run: dict[str, Any], steps: list[dict[str, Any]], *, now: datetime, threshold: timedelta,
           verifying_threshold: timedelta) -> RecoveryDecision | None:
    status = str(run.get("status") or "")
    last = _last_activity(run, steps)
    if last is None:
        return None
    if status == "verifying":
        if now - last < verifying_threshold:
            return None
        return RecoveryDecision(
            run_id=str(run["id"]),
            org_id=str(run["org_id"]),
            from_status=status,
            to_status="verification_inconclusive",
            reason=(
                "The write was accepted but its read-back did not finish "
                f"(no activity since {last.isoformat()}). Check the source system to confirm."
            ),
        )
    if status != "running" or now - last < threshold:
        return None
    in_flight = [s for s in steps if str(s.get("status") or "") == "running"]
    risky = [s for s in in_flight if _step_may_have_external_effect(s)]
    if risky:
        return RecoveryDecision(
            run_id=str(run["id"]),
            org_id=str(run["org_id"]),
            from_status=status,
            to_status="flagged_for_review",
            reason=(
                "Interrupted while a step that changes an external system was in progress "
                f"(no activity since {last.isoformat()}). It may or may not have taken effect: "
                "check the source system before retrying. Nothing was re-run."
            ),
            interrupted_steps=[str(s.get("id")) for s in in_flight],
            write_in_flight=True,
        )
    return RecoveryDecision(
        run_id=str(run["id"]),
        org_id=str(run["org_id"]),
        from_status=status,
        to_status="failed",
        reason=(
            f"Interrupted: no progress since {last.isoformat()} (worker restart or crash). "
            "No external change was in progress. Nothing was re-run."
        ),
        interrupted_steps=[str(s.get("id")) for s in in_flight],
    )


def _candidates(client: Any, cutoff: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 0
    while True:
        rows = (
            client.table("workflow_runs")
            .select("id,org_id,status,created_at,triggered_by")
            .in_("status", ["running", "verifying"])
            .lt("created_at", cutoff.isoformat())
            .order("created_at")
            .range(page * _PAGE, page * _PAGE + _PAGE - 1)
            .execute()
        ).data or []
        out.extend(rows)
        if len(rows) < _PAGE:
            return out
        page += 1


def _apply(client: Any, decision: RecoveryDecision, now: datetime) -> bool:
    from app.workflows.audit import write_audit_event

    updated = (
        client.table("workflow_runs")
        .update(
            {
                "status": decision.to_status,
                "completed_at": now.isoformat(),
                "error_message": decision.reason[:1000],
            }
        )
        .eq("id", decision.run_id)
        .eq("org_id", decision.org_id)
        .eq("status", decision.from_status)
        .execute()
    )
    if not (updated.data or []):
        return False  # the worker finished it, or another replica recovered it
    for step_id in decision.interrupted_steps:
        client.table("workflow_steps").update(
            {
                "status": "failed",
                "error_code": INTERRUPTED,
                "error_message": "Interrupted by a worker restart; not re-run",
                "completed_at": now.isoformat(),
                "is_retryable": not decision.write_in_flight,
            }
        ).eq("id", step_id).eq("status", "running").execute()
    try:
        from app.workflows.repository import mirror_legacy_run_to_contract

        mirror_legacy_run_to_contract(client, decision.run_id)
    except Exception as exc:  # noqa: BLE001
        logger.info("stale_run_mirror_skipped run_id=%s error=%s", decision.run_id, exc)
    write_audit_event(
        client,
        org_id=decision.org_id,
        actor_id="system:stale_run_recovery",
        action="workflow.run.recovered",
        resource_type="workflow_run",
        resource_id=decision.run_id,
        metadata=decision.as_dict(),
    )
    return True


def recover_stale_runs(
    client: Any,
    *,
    threshold_minutes: int = 60,
    verifying_threshold_minutes: int = 24 * 60,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    threshold = timedelta(minutes=max(5, threshold_minutes))
    verifying_threshold = timedelta(minutes=max(threshold_minutes, verifying_threshold_minutes))
    decisions: list[RecoveryDecision] = []
    for run in _candidates(client, now - threshold):
        steps = (
            client.table("workflow_steps")
            .select("id,step_type,status,created_at,started_at,completed_at,input_snapshot,output_snapshot")
            .eq("run_id", run["id"])
            .execute()
        ).data or []
        decision = decide(run, steps, now=now, threshold=threshold, verifying_threshold=verifying_threshold)
        if decision:
            decisions.append(decision)
    applied = 0
    if not dry_run:
        for decision in decisions:
            try:
                applied += 1 if _apply(client, decision, now) else 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("stale_run_recovery_failed run_id=%s error=%s", decision.run_id, exc)
    summary: dict[str, int] = {}
    for d in decisions:
        summary[d.to_status] = summary.get(d.to_status, 0) + 1
    return {
        "dry_run": dry_run,
        "candidates": len(decisions),
        "applied": applied,
        "by_outcome": summary,
        "runs": [d.as_dict() for d in decisions],
    }
