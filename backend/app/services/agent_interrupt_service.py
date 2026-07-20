"""Human-in-the-loop interrupt channel — pause/cancel before next tool/step (STA-108)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.workflows.audit import write_audit_event
from app.workflows.constants import RUN_STATUS_PAUSED

TargetType = Literal["agent_job", "workflow_run", "operator_session"]
InterruptSignal = Literal["pause", "cancel"]
InterruptSource = Literal["ui", "slack", "api"]

AUDIT_INTERRUPT_REQUESTED = "agent.interrupt.requested"
AUDIT_INTERRUPT_ACK = "agent.interrupt.acknowledged"


class AgentExecutionInterrupted(Exception):
    """Raised when execution must stop due to a human interrupt."""

    def __init__(self, signal: InterruptSignal, target_type: TargetType, target_id: str) -> None:
        self.signal = signal
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(f"Execution interrupted ({signal}) for {target_type}:{target_id}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_operator_session_target(client: Any, org_id: str, session_id: str) -> tuple[TargetType, str] | None:
    """Prefer a running agent job for the session, else an active workflow run."""
    jobs = (
        client.table("agent_jobs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("session_id", session_id)
        .in_("status", ["queued", "running", "paused"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if jobs:
        return "agent_job", str(jobs[0]["id"])
    runs = (
        client.table("workflow_runs")
        .select("id, status, parameters")
        .eq("org_id", org_id)
        .eq("status", "running")
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    for run in runs:
        params = run.get("parameters") if isinstance(run.get("parameters"), dict) else {}
        if str(params.get("operator_session_id") or "") == session_id:
            return "workflow_run", str(run["id"])
    if runs:
        return "workflow_run", str(runs[0]["id"])
    return None


def request_interrupt(
    client: Any,
    *,
    org_id: str,
    target_type: TargetType,
    target_id: str,
    signal: InterruptSignal,
    actor_id: str | None,
    source: InterruptSource = "ui",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue a pause/cancel interrupt for a running execution target."""
    if target_type == "operator_session":
        resolved = resolve_operator_session_target(client, org_id, target_id)
        if not resolved:
            raise ValueError("No running job or workflow found for session")
        target_type, target_id = resolved

    existing = (
        client.table("agent_execution_interrupts")
        .select("id")
        .eq("org_id", org_id)
        .eq("target_type", target_type)
        .eq("target_id", target_id)
        .eq("status", "pending")
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        client.table("agent_execution_interrupts").update(
            {"status": "expired", "acknowledged_at": _now()}
        ).eq("id", existing[0]["id"]).execute()

    row = {
        "org_id": org_id,
        "target_type": target_type,
        "target_id": target_id,
        "signal": signal,
        "status": "pending",
        "source": source,
        "requested_by": actor_id,
        "metadata": metadata or {},
    }
    inserted = client.table("agent_execution_interrupts").insert(row).execute()
    interrupt = dict(inserted.data[0]) if inserted.data else row

    if target_type == "agent_job":
        if signal == "cancel":
            client.table("agent_jobs").update({"status": "cancelled", "finished_at": _now(), "updated_at": _now()}).eq(
                "id", target_id
            ).eq("org_id", org_id).in_("status", ["queued", "running"]).execute()
        elif signal == "pause":
            client.table("agent_jobs").update({"status": "paused", "updated_at": _now()}).eq("id", target_id).eq(
                "org_id", org_id
            ).in_("status", ["queued", "running"]).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id or org_id,
        action=AUDIT_INTERRUPT_REQUESTED,
        resource_type=target_type,
        resource_id=target_id,
        metadata={"signal": signal, "source": source, "interruptId": str(interrupt.get("id"))},
    )
    return interrupt


def peek_pending_interrupt(
    client: Any, org_id: str, target_type: TargetType, target_id: str
) -> dict[str, Any] | None:
    rows = (
        client.table("agent_execution_interrupts")
        .select("*")
        .eq("org_id", org_id)
        .eq("target_type", target_type)
        .eq("target_id", target_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def acknowledge_interrupt(client: Any, interrupt_id: str) -> None:
    client.table("agent_execution_interrupts").update(
        {"status": "acknowledged", "acknowledged_at": _now()}
    ).eq("id", interrupt_id).execute()


def enforce_interrupt(
    client: Any,
    org_id: str,
    target_type: TargetType,
    target_id: str,
    *,
    actor_id: str | None = None,
) -> None:
    """Raise AgentExecutionInterrupted when a pending pause/cancel exists."""
    row = peek_pending_interrupt(client, org_id, target_type, target_id)
    if not row:
        return
    signal = str(row.get("signal") or "cancel")
    acknowledge_interrupt(client, str(row["id"]))
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id or org_id,
        action=AUDIT_INTERRUPT_ACK,
        resource_type=target_type,
        resource_id=target_id,
        metadata={"signal": signal, "interruptId": str(row["id"])},
    )
    if target_type == "workflow_run":
        if signal == "pause":
            # Non-terminal: repository update_run mirrors to contract runs.
            from app.workflows.repository import update_run

            update_run(client, target_id, status=RUN_STATUS_PAUSED)
        else:
            from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome

            finalize_execution_outcome(
                client,
                org_id=org_id,
                status="cancelled",
                source="api",
                actor_id=actor_id,
                run_id=target_id,
                error_summary="Interrupted by operator",
                verified_output=VerifiedOutputRef(
                    summary="Interrupted by operator",
                    result_url=f"/runs/{target_id}",
                    entity_type="workflow_run",
                    entity_id=target_id,
                ),
                metadata={"path": "agent_interrupt", "signal": signal},
            )
    raise AgentExecutionInterrupted(signal, target_type, target_id)  # type: ignore[arg-type]


def resolve_org_id_for_slack_team(client: Any, team_id: str) -> str | None:
    rows = (
        client.table("connectors")
        .select("org_id, config")
        .eq("type", "slack")
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    for row in rows:
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        if str(cfg.get("team_id") or cfg.get("teamId") or "") == team_id:
            return str(row["org_id"])
    return None
