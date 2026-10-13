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
# Runs are read in pages of RUN_PAGE_SIZE. A windowed read keeps paging until the
# window is exhausted or RUN_WINDOW_CEILING rows have been read; hitting the
# ceiling is reported (runsTruncated) instead of silently showing part of a month.
RUN_PAGE_SIZE = 1000
RUN_WINDOW_CEILING = 10_000
# Unwindowed reads keep the old "latest N" behaviour.
RUN_WINDOW_LIMIT = 200
ERROR_SNIPPET_LIMIT = 200
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
        schedule_type = str(row.get("schedule_type") or "recurring")
        tz_name = str(row.get("timezone") or "UTC")
        display_name = str(row.get("name") or "").strip()
        title = display_name or workflow_names.get(wf_id) or "Workflow schedule"
        subtitle = "One-time" if schedule_type == "once" else (cron_expr or None)
        item: dict[str, Any] = {
            "kind": "workflow",
            "id": schedule_id,
            "title": title,
            "subtitle": subtitle,
            "status": "enabled" if enabled else "disabled",
            "workflowId": wf_id or None,
            "scheduleType": schedule_type,
            "timezone": tz_name,
        }
        if cron_expr:
            item["cron"] = cron_expr
        if row.get("next_run_at"):
            item["nextRunAt"] = row.get("next_run_at")
        if row.get("last_run_at"):
            item["lastRunAt"] = row.get("last_run_at")
        if row.get("run_at"):
            item["runAt"] = row.get("run_at")
        if row.get("ends_at"):
            item["endsAt"] = row.get("ends_at")
        if row.get("name"):
            item["name"] = row.get("name")
        if enabled:
            item["occurrences"] = expand_cron_occurrences(
                cron_expr,
                window_start,
                window_end,
                tz_name=tz_name,
                ends_at=row.get("ends_at"),
                schedule_type=schedule_type,
                run_at=row.get("run_at") or row.get("next_run_at"),
            )
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
    runs: list[dict[str, Any]] | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[dict[str, Any]]:
    if runs is None:
        try:
            runs, _truncated = _windowed_runs(
                client,
                org_id,
                environment_name,
                workflow_id=workflow_id,
                window_start=window_start,
                window_end=window_end,
            )
        except Exception:  # noqa: BLE001
            return []
    items: list[dict[str, Any]] = []
    for run in runs:
        wf_id = str(run.get("workflow_id") or "")
        run_status = str(run.get("status") or "pending")
        mapped = RUN_STATUS_TO_SCHEDULED.get(run_status, "scheduled")
        wf_name = workflow_names.get(wf_id) or "workflow"
        # Prefix so blue task chips are not mistaken for purple workflow schedules.
        title = f"Run · {wf_name}"
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
        duration = run.get("duration_ms")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0:
            item["durationMs"] = int(duration)
        if mapped == "failed" and run.get("error_message"):
            item["error"] = _short_error(run.get("error_message"))
        if wf_id and workflow_names.get(wf_id):
            item["workflowName"] = workflow_names[wf_id]
        if run.get("trigger_type"):
            item["triggerType"] = str(run.get("trigger_type"))
        items.append(item)
    return items


def _short_error(value: Any, limit: int = ERROR_SNIPPET_LIMIT) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _windowed_runs(
    client: Any,
    org_id: str,
    environment_name: str,
    *,
    workflow_id: str | None,
    window_start: datetime | None,
    window_end: datetime | None,
    page_size: int = RUN_PAGE_SIZE,
    ceiling: int = RUN_WINDOW_CEILING,
) -> tuple[list[dict[str, Any]], bool]:
    """Runs started inside the requested window, newest first, and whether the read was cut short.

    With a window, pages through every run in it (so a month view shows the
    whole month) up to ``ceiling`` rows; ``True`` means the ceiling was hit and
    older runs in the window were left out. Without a window this is the latest
    ``RUN_WINDOW_LIMIT`` runs, as before, and is never reported as cut short.
    """

    def _query():
        q = (
            client.table("workflow_runs")
            .select(
                "id, workflow_id, status, run_type, created_at, completed_at, trigger_type, duration_ms, error_message"
            )
            .eq("org_id", org_id)
            .eq("environment", environment_name)
        )
        if window_start is not None:
            q = q.gte("created_at", window_start.isoformat())
        if window_end is not None:
            q = q.lt("created_at", window_end.isoformat())
        if workflow_id:
            q = q.eq("workflow_id", workflow_id)
        # id breaks created_at ties so pages never skip or repeat a run.
        return q.order("created_at", desc=True).order("id", desc=True)

    if window_start is None and window_end is None:
        return list(_query().limit(RUN_WINDOW_LIMIT).execute().data or []), False

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(rows) < ceiling:
        start = len(rows)
        page = list(_query().range(start, start + page_size - 1).execute().data or [])
        fresh = [row for row in page if str(row.get("id")) not in seen]
        for row in fresh:
            seen.add(str(row.get("id")))
        rows.extend(fresh)
        if len(page) < page_size or not fresh:
            return rows[:ceiling], False
    return rows[:ceiling], True


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
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Scheduled items in the window. Pass ``meta`` to learn whether runs were cut short (``runsTruncated``)."""
    selected_kinds = kinds or SCHEDULE_KINDS
    if meta is not None:
        meta["runsTruncated"] = False
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
        runs, truncated = _windowed_runs(
            client,
            org_id,
            environment_name,
            workflow_id=workflow_id,
            window_start=window_start,
            window_end=window_end,
        )
        if meta is not None:
            meta["runsTruncated"] = truncated
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
                runs=runs,
            )
        )

    if "job" in selected_kinds and workflow_id is None:
        jobs = list_training_jobs(client, org_id)
        dataset_ids = sorted({str(job.get("dataset_id") or "") for job in jobs if job.get("dataset_id")})
        dataset_names = _dataset_names_for_ids(client, org_id, dataset_ids)
        items.extend(_training_job_items(client, org_id, dataset_names=dataset_names))

    return items
