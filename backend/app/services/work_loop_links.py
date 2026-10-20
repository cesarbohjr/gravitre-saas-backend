"""Close the proposal -> Play run -> goal loop (flag ``work_loop_links_enabled``).

Reuses what is already there instead of a new link table:

* a Play run is tied to a work object the same way any run is: a
  ``work_object_events`` row per workflow run (``run_id``), the run ids in
  ``business_outcome_refs``, and ``work_object_id`` carried in the run's
  ``parameters.play`` so ``record_execution_work_object`` attributes the
  terminal outcome to that object instead of filing a new one;
* a goal is linked through ``work_objects.goal_id`` (migration
  20261012050000, flag ``goal_links_enabled``), which is what
  ``goal_link_progress`` already counts.

Every id a caller hands in is checked against the caller's org before it is
written. Nothing here starts work or bypasses an approval gate.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

# A proposal must be accepted first; archived and finished work is not restarted.
NOT_RUNNABLE_STATUSES = frozenset({"proposed", "archived", "completed"})
_STARTABLE_STATUSES = frozenset({"identified", "planned", "blocked", "failed"})


class WorkLoopLinkError(ValueError):
    """An id that is missing, foreign to the org, or in the wrong state."""


def work_loop_links_enabled(settings: Any) -> bool:
    return getattr(settings, "work_loop_links_enabled", False) is True


def goal_links_writable(settings: Any) -> bool:
    """Goal/entity columns exist only with the Phase 5 migration (goal_links_enabled)."""
    return work_loop_links_enabled(settings) and getattr(settings, "goal_links_enabled", False) is True


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _org_row(client: Any, table: str, org_id: str, row_id: str, columns: str = "id") -> dict[str, Any] | None:
    rows = client.table(table).select(columns).eq("org_id", org_id).eq("id", row_id).limit(1).execute().data or []
    return dict(rows[0]) if rows else None


def require_org_goal(client: Any, org_id: str, goal_id: str | None) -> str | None:
    goal_id = _clean(goal_id)
    if goal_id and _org_row(client, "goals", org_id, goal_id) is None:
        raise WorkLoopLinkError("goal not found")
    return goal_id


def require_org_business_entity(client: Any, org_id: str, entity_id: str | None) -> str | None:
    entity_id = _clean(entity_id)
    if entity_id and _org_row(client, "org_business_entities", org_id, entity_id) is None:
        raise WorkLoopLinkError("business entity not found")
    return entity_id


def require_runnable_work_object(client: Any, org_id: str, work_object_id: str) -> dict[str, Any]:
    row = _org_row(client, "work_objects", org_id, work_object_id, "*")
    if row is None:
        raise WorkLoopLinkError("work object not found")
    status = str(row.get("status") or "")
    if status in NOT_RUNNABLE_STATUSES:
        raise WorkLoopLinkError(
            "accept the proposal before running a Play for it"
            if status == "proposed"
            else f"work object is {status} and cannot start a Play run"
        )
    return row


def installation_goal_id(client: Any, org_id: str, play_key: str) -> str | None:
    """The goal an org's setup of this Play serves, if it names one."""
    rows = (
        client.table("play_installations")
        .select("goal_id, status, updated_at")
        .eq("org_id", org_id)
        .eq("play_key", play_key)
        .order("updated_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    for row in rows:
        if row.get("status") != "archived" and _clean(row.get("goal_id")):
            return str(row["goal_id"])
    return None


def play_run_work_object_id(settings: Any, parameters: Any) -> str | None:
    """The work object a Play run was started for, so its outcome lands there.

    Read only from ``parameters.play`` (written by the Play run route after an
    org check); ``record_execution_work_object`` still filters by org.
    """
    if not work_loop_links_enabled(settings) or not isinstance(parameters, dict):
        return None
    play = parameters.get("play")
    return _clean(play.get("work_object_id")) if isinstance(play, dict) else None


def resolve_run_links(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    work_object_id: str | None,
    business_entity_id: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a Play run's work object and entity; raise before anything starts."""
    work_object_id = _clean(work_object_id)
    business_entity_id = _clean(business_entity_id)
    if not (work_object_id or business_entity_id):
        return None, None
    if not work_loop_links_enabled(settings):
        raise WorkLoopLinkError("work loop links are not enabled")
    entity = require_org_business_entity(client, org_id, business_entity_id)
    work_object = require_runnable_work_object(client, org_id, work_object_id) if work_object_id else None
    if work_object is not None:
        linked_entity = _clean(work_object.get("business_entity_id"))
        if entity and linked_entity and entity != linked_entity:
            raise WorkLoopLinkError("business entity does not match the work object")
        entity = entity or linked_entity
    return work_object, entity


def link_play_run(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    work_object: dict[str, Any],
    play_run_id: str,
    play_key: str,
    workflow_runs: list[dict[str, Any]],
    actor_id: str | None,
    goal_id: str | None = None,
) -> bool:
    """Record that a Play run serves this work object. Never raises."""
    work_object_id = str(work_object.get("id") or "")
    try:
        run_ids = [str(r.get("runId")) for r in workflow_runs if r.get("runId")]
        for run in workflow_runs:
            client.table("work_object_events").insert(
                {
                    "org_id": org_id,
                    "work_object_id": work_object_id,
                    "run_id": run.get("runId") or None,
                    "event_type": "play_run_started",
                    "action_name": f"play.{play_key}",
                    "action_status": run.get("status"),
                    "evidence": {"run_url": f"/runs/{run.get('runId')}"} if run.get("runId") else {},
                    "audit_ref": {"source": "play_run", "play_run_id": play_run_id, "actor_id": actor_id},
                    "metadata": {
                        "play_key": play_key,
                        "play_run_id": play_run_id,
                        "workflow_id": run.get("workflowId"),
                        "approval_required": bool(run.get("approvalRequired")),
                    },
                }
            ).execute()
        refs = [str(r) for r in (work_object.get("business_outcome_refs") or []) if r]
        refs += [r for r in run_ids if r not in refs]
        metadata = safe_normalize_stored_dict(work_object.get("metadata"))
        play_runs = [p for p in (metadata.get("play_runs") or []) if isinstance(p, dict)]
        play_runs.append({"play_run_id": play_run_id, "play_key": play_key, "at": _now()})
        metadata["play_runs"] = play_runs[-20:]
        patch: dict[str, Any] = {
            "business_outcome_refs": refs,
            "metadata": metadata,
            "updated_at": _now(),
            "last_activity_at": _now(),
        }
        if str(work_object.get("status") or "") in _STARTABLE_STATUSES:
            awaiting = any(r.get("approvalRequired") for r in workflow_runs)
            patch["status"] = "awaiting_approval" if awaiting else "in_progress"
        goal_id = _clean(goal_id)
        if (
            goal_id
            and not _clean(work_object.get("goal_id"))
            and goal_links_writable(settings)
            and _org_row(client, "goals", org_id, goal_id) is not None
        ):
            # Inherit the objective's (or the Play setup's) goal, only from this org.
            patch["goal_id"] = goal_id
        client.table("work_objects").update(patch).eq("org_id", org_id).eq("id", work_object_id).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "work_loop_link_play_run_failed org_id=%s work_object_id=%s play_run_id=%s error=%s",
            org_id,
            work_object_id,
            play_run_id,
            exc,
        )
        return False


def play_run_request_for_proposal(
    client: Any,
    *,
    org_id: str,
    environment_name: str,
    work_object: dict[str, Any],
) -> dict[str, Any] | None:
    """What the client should POST to start the proposal's Play. Starts nothing.

    The run still goes through ``POST /api/plays/{key}/runs``, which keeps its
    operating-mode, readiness and approval-policy preflight.
    """
    metadata = safe_normalize_stored_dict(work_object.get("metadata"))
    proposal = safe_normalize_stored_dict(metadata, key="proposal")
    play_key = _clean(proposal.get("play_key"))
    if not play_key:
        return None
    from app.plays.catalog import get_platform_play

    if get_platform_play(play_key) is None:
        return None
    rows = (
        client.table("play_installations")
        .select("id, status, operating_mode")
        .eq("org_id", org_id)
        .eq("play_key", play_key)
        .eq("environment_name", environment_name)
        .limit(1)
        .execute()
        .data
        or []
    )
    installation = rows[0] if rows else None
    body: dict[str, Any] = {"workObjectId": str(work_object.get("id"))}
    entity = _clean(work_object.get("business_entity_id"))
    if entity:
        body["businessEntityId"] = entity
    request: dict[str, Any] = {
        "method": "POST",
        "path": f"/api/plays/{play_key}/runs",
        "playKey": play_key,
        "body": body,
        "approvalGated": True,
    }
    if installation:
        body["installationId"] = str(installation.get("id"))
        request["operatingMode"] = installation.get("operating_mode")
    else:
        request["blockedReason"] = "Set up this Play before running it."
    return request
