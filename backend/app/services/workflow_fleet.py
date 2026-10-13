"""Per-workflow run summary and department labels for the Workflows list.

Pure read helpers: they fold ``workflow_runs`` rows into the facts the list
shows (last run, whether a run is live, the most recent outcomes) and look up
which departments a workflow is assigned to. Nothing here starts or changes a run.
"""
from __future__ import annotations

from typing import Any, Iterable

RECENT_RUN_LIMIT = 12
LIVE_RUN_STATUSES = frozenset({"running"})


def summarize_runs(rows: Iterable[dict[str, Any]], *, recent_limit: int = RECENT_RUN_LIMIT) -> dict[str, dict[str, Any]]:
    """Fold run rows into one summary per workflow id.

    Rows may arrive in any order; they are sorted newest first here so the
    last run and its status are always the latest one, not the first row read.
    ``recentRuns`` lists up to ``recent_limit`` runs oldest to newest.
    """
    ordered = sorted(
        (row for row in rows if isinstance(row, dict) and row.get("workflow_id")),
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )
    out: dict[str, dict[str, Any]] = {}
    for row in ordered:
        key = str(row.get("workflow_id"))
        status = str(row.get("status") or "").strip().lower()
        summary = out.setdefault(
            key,
            {
                "count": 0,
                "completed": 0,
                "lastRun": None,
                "lastRunStatus": None,
                "isRunning": False,
                "recentRuns": [],
            },
        )
        summary["count"] += 1
        if status == "completed":
            summary["completed"] += 1
        if summary["lastRun"] is None:
            summary["lastRun"] = row.get("created_at")
            summary["lastRunStatus"] = status or None
        if status in LIVE_RUN_STATUSES:
            summary["isRunning"] = True
        if len(summary["recentRuns"]) < recent_limit:
            summary["recentRuns"].append({"status": status or "unknown", "createdAt": row.get("created_at")})
    for summary in out.values():
        summary["recentRuns"].reverse()
    return out


def workflow_department_names(client: Any, org_id: str, workflow_ids: list[str]) -> dict[str, list[str]]:
    """Department names each workflow is assigned to (empty when none or unreadable)."""
    if not workflow_ids:
        return {}
    try:
        assignments = (
            client.table("department_resource_assignments")
            .select("resource_id, department_id")
            .eq("org_id", org_id)
            .eq("resource_type", "workflow")
            .in_("resource_id", workflow_ids)
            .execute()
            .data
            or []
        )
        department_ids = sorted({str(row.get("department_id")) for row in assignments if row.get("department_id")})
        if not department_ids:
            return {}
        departments = (
            client.table("departments")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", department_ids)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 - department labels are optional on the list
        return {}
    names = {str(row.get("id")): str(row.get("name") or "").strip() for row in departments if row.get("id")}
    out: dict[str, list[str]] = {}
    for row in assignments:
        name = names.get(str(row.get("department_id")))
        resource_id = str(row.get("resource_id") or "")
        if not name or not resource_id:
            continue
        bucket = out.setdefault(resource_id, [])
        if name not in bucket:
            bucket.append(name)
    for bucket in out.values():
        bucket.sort()
    return out
