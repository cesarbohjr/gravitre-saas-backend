"""Unified schedules dashboard aggregation (workflow cron, runs, training jobs)."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.training_service import list_training_jobs
from app.workflows.cron import expand_cron_occurrences
from app.workflows.repository import list_org_workflow_schedules, workflow_names_for_ids

SCHEDULE_KINDS = frozenset({"workflow", "task", "job"})
RUN_STATUS_TO_SCHEDULED = {
    "pending": "queued",
    "pending_approval": "queued",
    "awaiting_approval": "queued",
    "approved": "queued",
    "running": "running",
    "paused": "running",
    "completed": "completed",
    "failed": "failed",
    "rejected": "failed",
    "cancelled": "failed",
}
JOB_STATUS_TO_SCHEDULED = {
    "queued": "queued",
    "training": "running",
    "completed": "completed",
    "failed": "failed",
}


def default_projection_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Current calendar month ± 1 week (UTC)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    window_start = month_start - timedelta(days=7)
    last_day = monthrange(now.year, now.month)[1]
    month_end = month_start.replace(day=last_day) + timedelta(days=1)
    window_end = month_end + timedelta(days=7)
    return window_start, window_end


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_kinds_param(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return SCHEDULE_KINDS
    selected = {part.strip().lower() for part in raw.split(",") if part.strip()}
    invalid = selected - SCHEDULE_KINDS
    if invalid:
        raise ValueError(f"Unsupported kinds: {', '.join(sorted(invalid))}")
    return frozenset(selected)


def _workflow_schedule_items(
    client: Any,
    org_id: str,
    environment_name: str,
    *,
    workflow_id: str | None,
    window_start: datetime,
    window_end: datetime,
    workflow_names: dict[str, str],
    schedules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in schedules:
        schedule_id = str(row["id"])
        wf_id = str(row.get("workflow_id") or "")
        cron_expr = str(row.get("cron_expression") or "").strip()
        enabled = bool(row.get("is_enabled", row.get("enabled", True)))
        title = workflow_names.get(wf_id) or "Workflow schedule"
        item: dict[str, Any] = {
            "kind": "workflow",
            "id": schedule_id,
            "title": title,
            "subtitle": cron_expr or None,
            "status": "enabled" if enabled else "disabled",
            "workflowId": wf_id or None,
        }
        if cron_expr:
            item["cron"] = cron_expr
        if row.get("next_run_at"):
            item["nextRunAt"] = row.get("next_run_at")
        if row.get("last_run_at"):
            item["lastRunAt"] = row.get("last_run_at")
        if enabled and cron_expr:
            item["occurrences"] = expand_cron_occurrences(cron_expr, window_start, window_end)
        else:
            item["occurrences"] = []
        items.append(item)
    return items


def _task_run_items(
    client: Any,
    org_id: str,
    environment_name: str,
    *,
    workflow_id: str | None,
    workflow_names: dict[str, str],
    limit: int = 200,
) -> list[dict[str, Any]]:
    q = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, run_type, created_at, completed_at, trigger_type")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if workflow_id:
        q = q.eq("workflow_id", workflow_id)
    try:
        response = q.execute()
    except Exception:  # noqa: BLE001
        return []
    runs = list(response.data or [])
    items: list[dict[str, Any]] = []
    for run in runs:
        wf_id = str(run.get("workflow_id") or "")
        run_status = str(run.get("status") or "pending")
        mapped = RUN_STATUS_TO_SCHEDULED.get(run_status, "scheduled")
        title = workflow_names.get(wf_id) or "Workflow run"
        subtitle_parts = [run_status.replace("_", " ")]
        if run.get("run_type"):
            subtitle_parts.append(str(run["run_type"]))
        item: dict[str, Any] = {
            "kind": "task",
            "id": str(run["id"]),
            "title": title,
            "subtitle": " · ".join(subtitle_parts),
            "status": mapped,
            "workflowId": wf_id or None,
        }
        if run.get("created_at"):
            item["startedAt"] = run.get("created_at")
        if run.get("completed_at"):
            item["completedAt"] = run.get("completed_at")
        items.append(item)
    return items


def _training_job_items(
    client: Any,
    org_id: str,
    *,
    dataset_names: dict[str, str],
) -> list[dict[str, Any]]:
    jobs = list_training_jobs(client, org_id)
    items: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("id") or "")
        status = str(job.get("status") or "queued")
        mapped = JOB_STATUS_TO_SCHEDULED.get(status, "scheduled")
        model_base = str(job.get("model_base") or "model")
        dataset_id = str(job.get("dataset_id") or "")
        dataset_name = dataset_names.get(dataset_id)
        item: dict[str, Any] = {
            "kind": "job",
            "id": job_id,
            "title": f"Training job ({model_base})",
            "subtitle": dataset_name or status,
            "status": mapped,
            "progress": int(job.get("progress") or 0),
        }
        if job.get("started_at"):
            item["startedAt"] = job.get("started_at")
        if job.get("completed_at"):
            item["completedAt"] = job.get("completed_at")
        items.append(item)
    return items


def _dataset_names_for_ids(client: Any, org_id: str, dataset_ids: list[str]) -> dict[str, str]:
    if not dataset_ids:
        return {}
    response = (
        client.table("training_datasets")
        .select("id, name")
        .eq("org_id", org_id)
        .in_("id", dataset_ids)
        .execute()
    )
    return {str(row["id"]): str(row.get("name") or "Dataset") for row in (response.data or [])}


def list_scheduled_items(
    client: Any,
    org_id: str,
    environment_name: str,
    *,
    workflow_id: str | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    kinds: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    selected_kinds = kinds or SCHEDULE_KINDS
    if window_start is None or window_end is None:
        default_start, default_end = default_projection_window()
        window_start = window_start or default_start
        window_end = window_end or default_end

    items: list[dict[str, Any]] = []
    workflow_ids: set[str] = set()

    schedules: list[dict[str, Any]] = []
    if "workflow" in selected_kinds:
        schedules = list_org_workflow_schedules(
            client,
            org_id,
            environment_name,
            workflow_id=workflow_id,
        )
        workflow_ids.update(str(row.get("workflow_id") or "") for row in schedules if row.get("workflow_id"))

    runs: list[dict[str, Any]] = []
    if "task" in selected_kinds:
        runs_q = (
            client.table("workflow_runs")
            .select("workflow_id")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .order("created_at", desc=True)
            .limit(200)
        )
        if workflow_id:
            runs_q = runs_q.eq("workflow_id", workflow_id)
        runs = list(runs_q.execute().data or [])
        workflow_ids.update(str(row.get("workflow_id") or "") for row in runs if row.get("workflow_id"))

    workflow_names = workflow_names_for_ids(client, org_id, sorted(workflow_ids))

    if "workflow" in selected_kinds:
        items.extend(
            _workflow_schedule_items(
                client,
                org_id,
                environment_name,
                workflow_id=workflow_id,
                window_start=window_start,
                window_end=window_end,
                workflow_names=workflow_names,
                schedules=schedules,
            )
        )

    if "task" in selected_kinds:
        items.extend(
            _task_run_items(
                client,
                org_id,
                environment_name,
                workflow_id=workflow_id,
                workflow_names=workflow_names,
            )
        )

    if "job" in selected_kinds and workflow_id is None:
        jobs = list_training_jobs(client, org_id)
        dataset_ids = sorted({str(job.get("dataset_id") or "") for job in jobs if job.get("dataset_id")})
        dataset_names = _dataset_names_for_ids(client, org_id, dataset_ids)
        items.extend(_training_job_items(client, org_id, dataset_names=dataset_names))

    return items
