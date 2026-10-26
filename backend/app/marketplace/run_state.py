"""Run state for installed Marketplace listings: is what the listing installed working right now.

An install points at the agents and workflows it created (installed_entity_* plus the
agentIds/operatorId/workflowIds metadata). A listing is "running" while one of them has
an agent job queued or running, or a workflow run in progress. Otherwise it is "idle".
The most recent run in the lookback window is returned as lastRunAt.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

LOOKBACK_DAYS = 30
ACTIVE_JOB_STATUSES = frozenset({"queued", "running"})
ACTIVE_RUN_STATUSES = frozenset({"pending", "approved", "running"})
_ROW_CAP = 2000


def _install_targets(install: dict[str, Any]) -> tuple[set[str], set[str]]:
    from app.marketplace.support import _metadata_id_list  # support imports browse, which imports this

    metadata = install.get("metadata") if isinstance(install.get("metadata"), dict) else {}
    entity_type = str(install.get("installed_entity_type") or "")
    entity_id = str(install.get("installed_entity_id") or "")
    agents = set(_metadata_id_list(metadata, plural_key="agentIds", singular_key="agentId"))
    if metadata.get("operatorId"):
        agents.add(str(metadata["operatorId"]))
    workflows = set(_metadata_id_list(metadata, plural_key="workflowIds", singular_key="workflowId"))
    if entity_id and entity_type in {"agent", "operator"}:
        agents.add(entity_id)
    if entity_id and entity_type == "workflow":
        workflows.add(entity_id)
    return agents, workflows


def _rows(fn: Any) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in (fn().data or [])]
    except Exception:  # noqa: BLE001 — run state is decoration; the catalog must still load
        return []


def _later(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return max(a, b)


def run_states_for_installs(
    client: Any,
    org_id: str,
    installs: dict[str, dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Map asset id to {runState, activeRunCount, lastRunAt} for each active install."""
    targets = {asset_id: _install_targets(row) for asset_id, row in installs.items()}
    agent_ids = set().union(*(a for a, _ in targets.values())) if targets else set()
    workflow_ids = set().union(*(w for _, w in targets.values())) if targets else set()
    if not agent_ids and not workflow_ids:
        return {asset_id: {"runState": "idle", "activeRunCount": 0, "lastRunAt": None} for asset_id in installs}

    since = ((now or datetime.now(UTC)) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    jobs = (
        _rows(
            lambda: client.table("agent_jobs")
            .select("status,created_at,agent_id:payload->>agent_id,operator_id:payload->>operator_id")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(_ROW_CAP)
            .execute()
        )
        if agent_ids
        else []
    )
    runs = (
        _rows(
            lambda: client.table("workflow_runs")
            .select("workflow_id,status,created_at")
            .eq("org_id", org_id)
            .in_("workflow_id", sorted(workflow_ids))
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(_ROW_CAP)
            .execute()
        )
        if workflow_ids
        else []
    )

    # Per entity: how many runs are in flight and when it last started one.
    active: dict[str, int] = {}
    last: dict[str, str] = {}
    for job in jobs:
        owner = str(job.get("agent_id") or job.get("operator_id") or "")
        if owner not in agent_ids:
            continue
        if job.get("status") in ACTIVE_JOB_STATUSES:
            active[owner] = active.get(owner, 0) + 1
        last[owner] = _later(last.get(owner), job.get("created_at")) or ""
    for run in runs:
        owner = str(run.get("workflow_id") or "")
        if run.get("status") in ACTIVE_RUN_STATUSES:
            active[owner] = active.get(owner, 0) + 1
        last[owner] = _later(last.get(owner), run.get("created_at")) or ""

    out: dict[str, dict[str, Any]] = {}
    for asset_id, (agents, workflows) in targets.items():
        owners = agents | workflows
        count = sum(active.get(o, 0) for o in owners)
        last_run: str | None = None
        for o in owners:
            last_run = _later(last_run, last.get(o) or None)
        out[asset_id] = {
            "runState": "running" if count else "idle",
            "activeRunCount": count,
            "lastRunAt": last_run,
        }
    return out
