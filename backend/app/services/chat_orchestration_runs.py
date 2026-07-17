"""Persist chat multi-step orchestrations as workflow_runs so timeline + /runs/[id] work."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.services.approval_record_service import create_contract_approval
from app.workflows.repository import create_run, create_step, update_run, update_step

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_hash(conversation_id: str, goal: str) -> str:
    raw = f"chat-orch|{conversation_id}|{goal}|{uuid4()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def start_orchestration_run(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    conversation_id: str,
    goal: str,
    steps: list[dict[str, Any]],
    environment_name: str = "production",
) -> str | None:
    """Create an execute run + steps for a chat orchestration. Returns run_id."""
    label = (goal or "Chat orchestration").strip()[:120] or "Chat orchestration"
    definition = {
        "name": label,
        "source": "chat_orchestration",
        "conversation_id": conversation_id,
        "steps": [
            {
                "id": str(step.get("step_id") or f"step_{idx}"),
                "name": str(step.get("label") or f"Step {idx}"),
                "type": "connector",
            }
            for idx, step in enumerate(steps, start=1)
        ],
    }
    parameters = {
        "source": "chat_orchestration",
        "conversation_id": conversation_id,
        "goal": goal,
        "label": label,
        "requested_by": user_id,
    }
    try:
        created = create_run(
            client,
            org_id=org_id,
            triggered_by=user_id,
            definition_snapshot=definition,
            parameters=parameters,
            run_hash=_run_hash(conversation_id, goal),
            workflow_id=None,
            environment_name=environment_name,
            # trigger_type constrained in DB — keep allowed value; source is in parameters.
            trigger_type="api",
            run_type="execute",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat orchestration run create failed: %s", exc)
        return None

    run_id = str(created.get("id") or "")
    if not run_id:
        return None

    # Mark approval as self-approved at plan confirm (chat "yes" / Approve plan).
    try:
        client.table("workflow_runs").update(
            {
                "approval_status": "approved",
                "status": "running",
                "required_approvals": 0,
            }
        ).eq("id", run_id).eq("org_id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat orchestration run approve stamp failed: %s", exc)

    for idx, step in enumerate(steps, start=1):
        step_key = str(step.get("step_id") or f"step_{idx}")
        step_name = str(step.get("label") or f"Step {idx}")
        try:
            create_step(
                client,
                run_id=run_id,
                org_id=org_id,
                step_id=step_key,
                step_index=idx - 1,
                step_name=step_name,
                step_type="connector",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat orchestration step create failed run=%s step=%s: %s", run_id, step_key, exc)

    try:
        create_contract_approval(
            client,
            org_id=org_id,
            title=f"Chat plan approved: {label}",
            description=(
                "Multi-step chat orchestration plan was approved in Chat. "
                f"Track execution on the run detail page."
            ),
            approval_type="connector_chat",
            priority="medium",
            status="approved",
            run_id=run_id,
            requested_by=user_id,
            context={
                "conversation_id": conversation_id,
                "gate_type": "chat_orchestration_plan",
                "entity": "Chat orchestration",
                "action": label,
                "run_id": run_id,
                "reviewed_by": user_id,
            },
            parameters=parameters,
        )
        # Stamp reviewer on the approvals row (create path may not set reviewed_*).
        client.table("approvals").update(
            {
                "reviewed_by": user_id,
                "reviewed_at": _now_iso(),
                "status": "approved",
            }
        ).eq("org_id", org_id).eq("run_id", run_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat orchestration approval audit failed run=%s: %s", run_id, exc)

    return run_id


def sync_orchestration_step(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    step_id: str,
    success: bool,
    summary: str | None = None,
    result_url: str | None = None,
    skipped: bool = False,
) -> None:
    if not run_id or not step_id:
        return
    try:
        rows = (
            client.table("workflow_steps")
            .select("id")
            .eq("run_id", run_id)
            .eq("org_id", org_id)
            .eq("step_id", step_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return
        step_uuid = str(rows[0]["id"])
        now = _now_iso()
        status = "skipped" if skipped else ("completed" if success else "failed")
        update_step(
            client,
            step_uuid,
            status=status,
            output_snapshot={
                "summary": summary,
                "result_url": result_url,
            },
            started_at=now,
            completed_at=now,
            error_message=None if (success or skipped) else (summary or "Step failed"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat orchestration step sync failed run=%s step=%s: %s", run_id, step_id, exc)


def finalize_orchestration_run(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    success: bool,
    summary: str | None = None,
) -> None:
    if not run_id:
        return
    try:
        update_run(
            client,
            run_id,
            status="completed" if success else "failed",
            completed_at=_now_iso(),
            error_message=None if success else (summary or "Orchestration failed"),
            approval_status="approved",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat orchestration run finalize failed run=%s: %s", run_id, exc)


def resolve_orchestration_result_url(
    *,
    run_id: str | None,
    step_results: list[dict[str, Any]],
    conversation_id: str,
) -> str:
    """Never bounce successful orchestration back to /ai alone."""
    for row in reversed(step_results or []):
        url = str(row.get("url") or "").strip()
        if not url or url in {"/ai", "/connectors"}:
            continue
        if url.startswith("http://") or url.startswith("https://") or url.startswith("/"):
            # Prefer durable Gravitre run page when we have one; keep external vendor links
            # as secondary via the run detail page.
            if run_id and not url.startswith("http"):
                return f"/runs/{run_id}"
            if run_id and url.startswith("http"):
                return f"/runs/{run_id}"
            return url
    if run_id:
        return f"/runs/{run_id}"
    return f"/ai?conversation={conversation_id}"
