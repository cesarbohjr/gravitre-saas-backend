"""Per-workflow run summary and department labels for the Workflows list.

Pure read helpers: they fold ``workflow_runs`` rows into the facts the list
shows (last run, whether a run is live, the most recent outcomes) and look up
which departments a workflow is assigned to. Nothing here starts or changes a run.
"""
from __future__ import annotations

from typing import Any, Iterable

RECENT_RUN_LIMIT = 12
LIVE_RUN_STATUSES = frozenset({"running"})
RUN_PAGE_SIZE = 1000
# Past this many runs the list stops counting and says so (runStatsComplete:
# false) rather than publishing a success rate computed from part of the history.
RUN_HISTORY_CEILING = 20_000


def read_run_history(client: Any, *, org_id: str, environment_name: str, workflow_ids: list[str]) -> tuple[list[dict[str, Any]], bool]:
    """Every run of these workflows, newest first, in pages; and whether the ceiling cut it short.

    PostgREST caps a single unbounded select (often at 1,000 rows), which would
    silently undercount runs and skew success rates for a busy org, so the
    history is paged explicitly. Reaching the ceiling probes one more row, so a
    history of exactly RUN_HISTORY_CEILING runs is reported complete.
    """
    if not workflow_ids:
        return [], False

    def query():
        return (
            client.table("workflow_runs")
            .select("id, workflow_id, status, created_at")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .in_("workflow_id", workflow_ids)
            .order("created_at", desc=True)
            .order("id", desc=True)
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(rows) < RUN_HISTORY_CEILING:
        start = len(rows)
        want = min(RUN_PAGE_SIZE, RUN_HISTORY_CEILING - start)
        page = list(query().range(start, start + want - 1).execute().data or [])
        fresh = [row for row in page if str(row.get("id")) not in seen]
        for row in fresh:
            seen.add(str(row.get("id")))
        rows.extend(fresh)
        if len(page) < want or not fresh:
            return rows, False
    probe = list(query().range(RUN_HISTORY_CEILING, RUN_HISTORY_CEILING).execute().data or [])
    return rows, any(str(row.get("id")) not in seen for row in probe)


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
