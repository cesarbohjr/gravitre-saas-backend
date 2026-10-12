"""Phase 5: the one write path for goals.

The Next.js goal routes wrote ``goals`` directly with the user's Supabase
client while FastAPI wrote objectives through the composer: two CRUD paths.
These functions serve the same request and response shapes as the Next routes
(camelCase rows, ``{goal}`` / ``{goals}``), so the routes can proxy here
(``GOALS_BACKEND_WRITES=true`` on the web app) without the UI changing.

Progress from links: a goal's completion counts the work objects and agent
jobs linked to it by ``goal_id`` (never keyword guesses). Proposed and
archived work does not count; with nothing linked, completion stays ``None``.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

GOAL_STATUSES = frozenset({"draft", "active", "paused", "completed", "cancelled"})
TEXT_FIELDS = ("objective", "category", "priority", "frequency", "department", "status")
_CAMEL = re.compile(r"_([a-z])")
_SNAKE = re.compile(r"[A-Z]")

WORK_DONE = frozenset({"completed"})
WORK_NOT_COUNTED = frozenset({"proposed", "archived"})
JOB_DONE = frozenset({"completed"})
JOB_NOT_COUNTED = frozenset({"cancelled"})


class GoalValidationError(ValueError):
    pass


def to_camel(row: dict[str, Any]) -> dict[str, Any]:
    """Top-level keys only, like the web app's ``snakeToCamel``."""
    return {_CAMEL.sub(lambda m: m.group(1).upper(), k): v for k, v in row.items()}


def to_snake(body: dict[str, Any]) -> dict[str, Any]:
    return {_SNAKE.sub(lambda m: f"_{m.group(0).lower()}", k): v for k, v in body.items()}


def _clean_fields(snake: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in TEXT_FIELDS:
        if key in snake:
            value = snake[key]
            out[key] = None if value is None else str(value)
    if "objective" in out:
        out["objective"] = (out["objective"] or "").strip()
        if not out["objective"]:
            raise GoalValidationError("objective is required")
    if out.get("status") is not None and out["status"] not in GOAL_STATUSES:
        raise GoalValidationError(f"status must be one of {sorted(GOAL_STATUSES)}")
    if "success_metrics" in snake:
        if not isinstance(snake["success_metrics"], dict):
            raise GoalValidationError("successMetrics must be an object")
        out["success_metrics"] = snake["success_metrics"]
    if "connected_systems" in snake:
        systems = snake["connected_systems"]
        if not isinstance(systems, list):
            raise GoalValidationError("connectedSystems must be a list")
        out["connected_systems"] = [str(s) for s in systems]
    return out


def list_goals(client: Any, org_id: str) -> list[dict[str, Any]]:
    res = client.table("goals").select("*").eq("org_id", org_id).order("created_at", desc=True).execute()
    return [to_camel(r) for r in res.data or [] if isinstance(r, dict)]


def get_goal(client: Any, org_id: str, goal_id: str) -> dict[str, Any] | None:
    res = client.table("goals").select("*").eq("org_id", org_id).eq("id", goal_id).limit(1).execute()
    rows = [r for r in res.data or [] if isinstance(r, dict)]
    return to_camel(rows[0]) if rows else None


def create_goal(client: Any, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
    fields = _clean_fields(to_snake(body))
    if not fields.get("objective"):
        raise GoalValidationError("objective is required")
    row = {
        "org_id": org_id,
        "objective": fields["objective"],
        "category": fields.get("category"),
        "priority": fields.get("priority"),
        "frequency": fields.get("frequency"),
        "department": fields.get("department"),
        "success_metrics": fields.get("success_metrics", {}),
        "connected_systems": fields.get("connected_systems", []),
        "status": fields.get("status") or "draft",
    }
    res = client.table("goals").insert(row).execute()
    return to_camel((res.data or [row])[0])


def update_goal(client: Any, org_id: str, goal_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
    fields = _clean_fields(to_snake(body))
    if not fields:
        raise GoalValidationError("No updatable fields were provided")
    fields["updated_at"] = datetime.now(UTC).isoformat()
    res = client.table("goals").update(fields).eq("org_id", org_id).eq("id", goal_id).execute()
    rows = [r for r in res.data or [] if isinstance(r, dict)]
    return to_camel(rows[0]) if rows else None


def goal_link_progress(client: Any, org_id: str, goal_id: str) -> dict[str, Any]:
    """Completion from linked work, with the counts behind it."""
    work = (
        client.table("work_objects")
        .select("id, status, title")
        .eq("org_id", org_id)
        .eq("goal_id", goal_id)
        .limit(500)
        .execute()
        .data
        or []
    )
    jobs = (
        client.table("agent_jobs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("goal_id", goal_id)
        .limit(500)
        .execute()
        .data
        or []
    )
    counted_work = [w for w in work if w.get("status") not in WORK_NOT_COUNTED]
    counted_jobs = [j for j in jobs if j.get("status") not in JOB_NOT_COUNTED]
    total = len(counted_work) + len(counted_jobs)
    done = sum(1 for w in counted_work if w.get("status") in WORK_DONE) + sum(
        1 for j in counted_jobs if j.get("status") in JOB_DONE
    )

    def _by_status(rows: list[dict[str, Any]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows:
            key = str(r.get("status") or "unknown")
            out[key] = out.get(key, 0) + 1
        return out

    return {
        "goalId": goal_id,
        "basis": "linked_work",
        "completionPercentage": round(100 * done / total) if total else None,
        "linkedWork": {"total": len(work), "byStatus": _by_status(work)},
        "linkedJobs": {"total": len(jobs), "byStatus": _by_status(jobs)},
        "proposedWork": sum(1 for w in work if w.get("status") == "proposed"),
    }
