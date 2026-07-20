"""Canonical Execution Outcome Record (Module A / STA-329).

Single write authority for every terminal execution state. Surfaces (Runs,
Notifications, Audit, Failure Alerts, learning) are READ MODELS off this
fanout — they must not write their own outcome state independently.

Pattern mirrors catalog_write_authority: one module, every surface calls in.

Schema decision (finishes STA-271 residual):
  - Customer-facing canonical run identity: contract ``runs`` (STA-272).
  - Terminal writes go only through ``repository.update_run``, which updates
    ``workflow_runs`` then mirrors into ``runs`` / ``run_steps``.
  - No surface may insert/update either table for terminal outcomes outside
    this module. Dual-write is contained inside the repository façade only;
    invert primary write to ``runs`` is a follow-on cutover, not a second
    outcome writer.

Audit decision (finishes STA-274 residual for this path):
  - Keep both tables (see docs/delivery/module-a-audit-store-decision.md).
  - Sole writer: ``write_audit_event`` (dual-writes audit_logs + audit_events).
  - Customer-facing canonical read store remains ``audit_logs``.
  - ``audit_events`` remains metrics / tool-invoke stream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from app.core.logging import get_logger
from app.workflows.constants import (
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PARTIAL_SUCCESS,
)

logger = get_logger(__name__)

# Versioned training substrate — bump + changelog when wire shape changes.
# See docs/delivery/module-a-outcome-schema-changelog.md
OUTCOME_SCHEMA_VERSION = "1.0.0"

TerminalStatus = Literal["completed", "failed", "cancelled", "partial_success"]
OutcomeSource = Literal[
    "chat_orch",
    "assistant_chat",
    "canvas",
    "api",
    "worker",
    "assignment",
]

TERMINAL_STATUSES = frozenset(
    {
        RUN_STATUS_COMPLETED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
        RUN_STATUS_PARTIAL_SUCCESS,
    }
)


@dataclass(frozen=True)
class VerifiedOutputRef:
    """Verified-output convention: real summary and/or result_url — never a bare success flag."""

    summary: str | None = None
    result_url: str | None = None
    external_url: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    integration: str | None = None

    def as_entity_ref(self, *, run_id: str | None) -> dict[str, Any]:
        ref: dict[str, Any] = {}
        if self.entity_type:
            ref["entity_type"] = self.entity_type
        elif run_id:
            ref["entity_type"] = "workflow_run"
        if self.entity_id:
            ref["entity_id"] = self.entity_id
        elif run_id:
            ref["entity_id"] = run_id
        if self.result_url:
            ref["result_url"] = self.result_url
        elif run_id:
            ref["result_url"] = f"/runs/{run_id}"
        if self.external_url:
            ref["external_url"] = self.external_url
        if self.integration:
            ref["integration"] = self.integration
        return ref


@dataclass
class ExecutionOutcomeEvent:
    """One outcome event shape — minimum fields for Module A."""

    org_id: str
    status: TerminalStatus
    source: OutcomeSource
    actor_id: str | None = None
    run_id: str | None = None
    workflow_id: str | None = None
    error_summary: str | None = None
    timestamp: str | None = None
    verified_output: VerifiedOutputRef | None = None
    notification_title: str | None = None
    notification_body: str | None = None
    email_context: dict[str, Any] | None = None
    channel_hints: dict[str, bool] = field(
        default_factory=lambda: {"bell": True, "email": False}
    )
    approval_status: str | None = None
    persist_run: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FinalizeExecutionOutcomeResult:
    status: str
    run_id: str | None
    audit_action: str | None
    notification_event: str | None
    learning_event: str | None
    timestamp: str
    fanout: dict[str, bool]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(status: str) -> TerminalStatus:
    normalized = str(status or "").strip().lower()
    if normalized == RUN_STATUS_PARTIAL_SUCCESS:
        return "partial_success"
    if normalized == RUN_STATUS_CANCELLED:
        return "cancelled"
    if normalized == RUN_STATUS_FAILED:
        return "failed"
    if normalized == RUN_STATUS_COMPLETED:
        return "completed"
    raise ValueError(
        f"finalize_execution_outcome requires a terminal status; got {status!r}"
    )


def is_terminal_run_status(status: str) -> bool:
    return str(status or "").strip().lower() in TERMINAL_STATUSES


def _audit_action_for(status: TerminalStatus) -> str:
    if status == "failed":
        return "workflow.execute.failed"
    if status == "cancelled":
        return "workflow.execute.cancelled"
    return "workflow.execute.completed"


def _notification_event_for(status: TerminalStatus) -> str:
    if status == "failed":
        return "run_failed"
    if status == "cancelled":
        return "run_cancelled"
    return "run_completed"


def _learning_event_for(status: TerminalStatus) -> str:
    if status == "failed":
        return "workflow_failed"
    if status == "cancelled":
        return "workflow_cancelled"
    return "workflow_executed"


def _default_title(status: TerminalStatus, *, source: OutcomeSource) -> str:
    from app.services.gravitree_voice import format_operator_message

    return format_operator_message(
        "notification_run_title",
        status=status,
        source=source,
    )


def _default_body(event: ExecutionOutcomeEvent, status: TerminalStatus) -> str:
    from app.services.gravitree_voice import format_operator_message

    verified_summary = (
        event.verified_output.summary if event.verified_output else None
    )
    # Prefer explicit body; fall back to caller title detail (never bypass voice).
    body = event.notification_body or (
        event.notification_title if status != "failed" else None
    )
    return format_operator_message(
        "notification_run_body",
        status=status,
        body=body,
        error_summary=event.error_summary,
        verified_summary=verified_summary,
    )


def _audit_summary(event: ExecutionOutcomeEvent, status: TerminalStatus) -> str | None:
    """Voice-shape audit-facing failure summaries via Module D (raw detail preserved in metadata)."""
    raw = (event.error_summary or "").strip()
    if not raw:
        return event.error_summary
    if status != "failed":
        return event.error_summary
    from app.services.gravitree_voice import format_operator_message

    return format_operator_message(
        "audit_failure_summary",
        error_summary=raw,
        source=event.source,
    )

def _persist_run(client: Any, event: ExecutionOutcomeEvent, status: TerminalStatus, ts: str) -> None:
    if not event.persist_run or not event.run_id:
        return
    from app.workflows.repository import update_run

    auditish = _audit_summary(event, status) if status == "failed" else event.error_summary
    update_run(
        client,
        event.run_id,
        status=status,
        completed_at=ts,
        error_message=auditish if status == "failed" else event.error_summary,
        approval_status=event.approval_status,
    )


def _write_audit(client: Any, event: ExecutionOutcomeEvent, status: TerminalStatus) -> str | None:
    actor = event.actor_id
    if not actor:
        logger.warning(
            "execution_outcome_audit_skipped source=%s status=%s reason=no_actor",
            event.source,
            status,
        )
        return None

    voiced_error = _audit_summary(event, status) if status == "failed" else event.error_summary
    resource_id = event.run_id
    if resource_id:
        from app.workflows.repository import (
            emit_execute_cancelled,
            emit_execute_completed,
            emit_execute_failed,
        )

        if status == "failed":
            emit_execute_failed(client, event.org_id, actor, resource_id, voiced_error)
        elif status == "cancelled":
            emit_execute_cancelled(client, event.org_id, actor, resource_id)
        else:
            emit_execute_completed(client, event.org_id, actor, resource_id, status)
        return _audit_action_for(status)

    # Assistant/connector paths without a workflow run still need audit integrity.
    from app.workflows.audit import write_audit_event

    vo = event.verified_output
    resource_id = (vo.entity_id if vo else None) or event.metadata.get("conversation_id")
    if not resource_id:
        logger.warning(
            "execution_outcome_audit_skipped source=%s status=%s reason=no_resource",
            event.source,
            status,
        )
        return None
    action = _audit_action_for(status)
    write_audit_event(
        client,
        org_id=event.org_id,
        actor_id=actor,
        action=action,
        resource_type=(vo.entity_type if vo and vo.entity_type else "execution"),
        resource_id=resource_id,
        metadata={
            "source": event.source,
            "status": status,
            "error_message": (voiced_error or "")[:200],
            "error_message_raw": (event.error_summary or "")[:200],
            **dict(event.metadata or {}),
        },
    )
    return action


def _emit_notification(
    client: Any,
    event: ExecutionOutcomeEvent,
    status: TerminalStatus,
) -> str | None:
    actor = event.actor_id
    if not actor:
        logger.warning(
            "execution_outcome_notify_skipped source=%s status=%s reason=no_actor run=%s",
            event.source,
            status,
            event.run_id,
        )
        return None

    from app.services.notification_emitter import emit_notification

    notify_event = _notification_event_for(status)
    verified = event.verified_output or VerifiedOutputRef()
    # Always Module D house titles — caller notification_title must not bypass voice.
    emit_notification(
        client,
        org_id=event.org_id,
        user_id=actor,
        event_type=notify_event,
        title=_default_title(status, source=event.source),
        body=_default_body(event, status),
        entity_ref=verified.as_entity_ref(run_id=event.run_id),
        channel_hints=dict(event.channel_hints or {"bell": True, "email": False}),
        email_context=event.email_context,
    )
    return notify_event


def _resolve_workflow_id(client: Any, event: ExecutionOutcomeEvent) -> str | None:
    if event.workflow_id:
        return str(event.workflow_id)
    if not event.run_id:
        return None
    try:
        row = (
            client.table("workflow_runs")
            .select("workflow_id")
            .eq("id", event.run_id)
            .eq("org_id", event.org_id)
            .limit(1)
            .execute()
        )
        return str((row.data or [{}])[0].get("workflow_id") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _record_learning(client: Any, event: ExecutionOutcomeEvent, status: TerminalStatus, ts: str) -> str | None:
    """Record learning on EVERY terminal state (not success-only). Sync-safe."""
    learning_event = _learning_event_for(status)
    workflow_id = event.workflow_id or ""
    run_id = event.run_id or ""
    payload = {
        "id": str(uuid4()),
        "org_id": event.org_id,
        "outcome_event": learning_event,
        "entity_type": "workflow" if (workflow_id or run_id) else "execution",
        "entity_id": workflow_id or run_id or event.source,
        "workflow_id": workflow_id or None,
        "workflow_run_id": run_id or None,
        "metadata": {
            **dict(event.metadata or {}),
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "source": event.source,
            "terminal_status": status,
            "error": event.error_summary,
            "verified_summary": (event.verified_output.summary if event.verified_output else None),
            "result_url": (event.verified_output.result_url if event.verified_output else None),
            "integration": (
                event.verified_output.integration
                if event.verified_output and event.verified_output.integration
                else (event.metadata or {}).get("integration")
            ),
            "cancelled": status == "cancelled",
        },
        "measured_at": ts,
        "measurement_status": "recorded",
        "created_at": ts,
    }

    try:
        client.table("intelligence_outcome_events").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "execution_outcome_learning_skipped org_id=%s run_id=%s error=%s",
            event.org_id,
            event.run_id,
            exc,
        )
        return None
    return learning_event


def _enqueue_failure_alert_correlation(client: Any, event: ExecutionOutcomeEvent, status: TerminalStatus) -> bool:
    """Failure Alerts remains a distinct product; subscribe to real outcomes here."""
    if status != "failed":
        return False
    try:
        from app.services.workflow_failure_prediction_service import (
            correlate_observed_run_failure,
        )

        integration = (
            event.verified_output.integration
            if event.verified_output and event.verified_output.integration
            else (event.metadata or {}).get("integration")
        )
        return bool(
            correlate_observed_run_failure(
                client,
                org_id=event.org_id,
                workflow_id=event.workflow_id,
                run_id=event.run_id,
                error_summary=event.error_summary,
                source=event.source,
                connector_id=(event.metadata or {}).get("connector_id"),
                action_type=(event.metadata or {}).get("action_type")
                or (event.metadata or {}).get("invoke_action"),
                integration=str(integration).strip() if integration else None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "execution_outcome_failure_alert_correlation_skipped run_id=%s error=%s",
            event.run_id,
            exc,
        )
        return False


def _coerce_verified_output(
    verified_output: VerifiedOutputRef | dict[str, Any] | None,
) -> VerifiedOutputRef | None:
    if verified_output is None:
        return None
    if isinstance(verified_output, VerifiedOutputRef):
        return verified_output
    if isinstance(verified_output, dict):
        return VerifiedOutputRef(
            summary=verified_output.get("summary"),
            result_url=verified_output.get("result_url"),
            external_url=verified_output.get("external_url"),
            entity_type=verified_output.get("entity_type"),
            entity_id=verified_output.get("entity_id"),
            integration=verified_output.get("integration"),
        )
    return None


def finalize_execution_outcome(
    client: Any,
    event: ExecutionOutcomeEvent | None = None,
    /,
    *,
    org_id: str | None = None,
    status: str | None = None,
    source: OutcomeSource | None = None,
    actor_id: str | None = None,
    run_id: str | None = None,
    workflow_id: str | None = None,
    error_summary: str | None = None,
    verified_output: VerifiedOutputRef | dict[str, Any] | None = None,
    notification_title: str | None = None,
    notification_body: str | None = None,
    email_context: dict[str, Any] | None = None,
    channel_hints: dict[str, bool] | None = None,
    approval_status: str | None = None,
    persist_run: bool = True,
    metadata: dict[str, Any] | None = None,
) -> FinalizeExecutionOutcomeResult:
    """Atomic fanout for one terminal execution outcome.

    1. Persist/update the canonical run row (via repository.update_run → mirror).
    2. Write audit via write_audit_event (STA-274 single writer).
    3. Emit notification with REAL event type (run_failed / run_completed / run_cancelled).
    4. Record learning outcome on EVERY terminal state.
    5. Enqueue failure-alert correlation as a subscriber (failures only).
    """
    if event is None:
        if not org_id or not status or not source:
            raise ValueError("org_id, status, and source are required")
        event = ExecutionOutcomeEvent(
            org_id=org_id,
            status=_normalize_status(status),
            source=source,
            actor_id=actor_id,
            run_id=run_id,
            workflow_id=workflow_id,
            error_summary=error_summary,
            verified_output=_coerce_verified_output(verified_output),
            notification_title=notification_title,
            notification_body=notification_body,
            email_context=email_context,
            channel_hints=channel_hints or {"bell": True, "email": False},
            approval_status=approval_status,
            persist_run=persist_run,
            metadata=dict(metadata or {}),
        )

    terminal = _normalize_status(event.status)
    ts = event.timestamp or _now_iso()
    if not event.workflow_id:
        event.workflow_id = _resolve_workflow_id(client, event)
    fanout = {
        "run_persisted": False,
        "audit_written": False,
        "notification_emitted": False,
        "learning_recorded": False,
        "failure_alert_correlated": False,
    }
    audit_action: str | None = None
    notification_event: str | None = None
    learning_event: str | None = None

    try:
        _persist_run(client, event, terminal, ts)
        fanout["run_persisted"] = bool(event.persist_run and event.run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "execution_outcome_run_persist_failed run_id=%s error=%s",
            event.run_id,
            exc,
        )

    try:
        audit_action = _write_audit(client, event, terminal)
        fanout["audit_written"] = bool(audit_action)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "execution_outcome_audit_failed run_id=%s error=%s",
            event.run_id,
            exc,
        )

    try:
        notification_event = _emit_notification(client, event, terminal)
        fanout["notification_emitted"] = bool(notification_event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "execution_outcome_notification_failed run_id=%s error=%s",
            event.run_id,
            exc,
        )

    try:
        learning_event = _record_learning(client, event, terminal, ts)
        fanout["learning_recorded"] = bool(learning_event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "execution_outcome_learning_failed run_id=%s error=%s",
            event.run_id,
            exc,
        )

    try:
        fanout["failure_alert_correlated"] = _enqueue_failure_alert_correlation(
            client, event, terminal
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "execution_outcome_failure_alert_failed run_id=%s error=%s",
            event.run_id,
            exc,
        )

    stream_payload = {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "org_id": event.org_id,
        "run_id": event.run_id,
        "workflow_id": event.workflow_id,
        "status": terminal,
        "source": event.source,
        "actor_id": event.actor_id,
        "error_summary": event.error_summary,
        "timestamp": ts,
        "verified_output": (
            {
                "summary": event.verified_output.summary,
                "result_url": event.verified_output.result_url,
                "external_url": event.verified_output.external_url,
                "entity_type": event.verified_output.entity_type,
                "entity_id": event.verified_output.entity_id,
                "integration": event.verified_output.integration,
            }
            if event.verified_output
            else None
        ),
        "audit_action": audit_action,
        "notification_event": notification_event,
        "learning_event": learning_event,
        "fanout": fanout,
    }
    try:
        from app.services.outcome_event_bus import publish_outcome

        publish_outcome(event.org_id, stream_payload)
        fanout["outcome_stream_published"] = True
    except Exception as exc:  # noqa: BLE001
        fanout["outcome_stream_published"] = False
        logger.debug(
            "execution_outcome_stream_publish_skipped run_id=%s error=%s",
            event.run_id,
            exc,
        )

    logger.info(
        "execution_outcome_finalized org_id=%s run_id=%s status=%s source=%s "
        "schema_version=%s fanout=%s",
        event.org_id,
        event.run_id,
        terminal,
        event.source,
        OUTCOME_SCHEMA_VERSION,
        fanout,
    )
    return FinalizeExecutionOutcomeResult(
        status=terminal,
        run_id=event.run_id,
        audit_action=audit_action,
        notification_event=notification_event,
        learning_event=learning_event,
        timestamp=ts,
        fanout=fanout,
    )
