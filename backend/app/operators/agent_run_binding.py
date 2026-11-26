"""Resolve only a server-persisted job/run association."""
from app.workflows.repository import get_run_with_steps


def resolve_bound_run(client, job, *, for_execution=False):
    run_id = job.get("bound_run_id")
    if not run_id:
        return None
    environment = job.get("environment")
    actor = job.get("created_by")
    if not environment or not actor or not job.get("org_id"):
        raise ValueError("Incomplete persisted job run identity")
    run = get_run_with_steps(client, str(job["org_id"]), str(run_id), environment)
    if not run or str(run.get("triggered_by")) != str(actor):
        raise ValueError("Invalid persisted job run identity")
    if for_execution and (run.get("parameters") or {}).get("assignment_tracking_only") is True:
        # Tracking is not a sealed action approval. Preserve the ordinary action gate.
        return None
    return str(run_id)



def resolve_completed_agent_play_lineage(client, *, org_id, actor_id, environment,
                                         job_id, opportunity_id, source_run_ids,
                                         play_key, installation_id, workflow_id):
    """Advisory attribution only, independently scoped to a completed job and run.

    The original task's structured handoff request must match the freshly
    selected opportunity. Neither task input nor agent output grants approval.
    """
    from uuid import UUID
    from app.operators.agent_jobs import get_job

    try:
        job_id = str(UUID(str(job_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Agent handoff unavailable") from None
    if not org_id or not actor_id or not environment:
        raise ValueError("Agent handoff unavailable")
    job = get_job(client, org_id, job_id)
    if (not job or str(job.get("org_id")) != str(org_id)
            or str(job.get("created_by")) != str(actor_id)
            or job.get("environment") != environment
            or job.get("kind") not in {"agent_task", "operator_task"}
            or job.get("status") != "completed" or not job.get("finished_at")):
        raise ValueError("Agent handoff unavailable")
    result = job.get("result")
    if (not isinstance(result, dict) or result.get("aiStatus") != "ok"
            or result.get("react_status") != "completed" or result.get("error")
            or result.get("needs_human_input") or result.get("requires_approval")):
        raise ValueError("Agent handoff unavailable")
    run_id = resolve_bound_run(client, job)
    run = get_run_with_steps(client, org_id, run_id, environment) if run_id else None
    params = run.get("parameters") if run else None
    if (not run or run.get("status") != "completed" or not isinstance(params, dict)
            or params.get("assignment_tracking_only") is not True
            or params.get("outcome_finalized") is not True):
        raise ValueError("Agent handoff unavailable")
    payload = job.get("payload")
    context = payload.get("context") if isinstance(payload, dict) else None
    requested = context.get("play_handoff") if isinstance(context, dict) else None
    expected = {"opportunity_id": opportunity_id, "source_run_ids": dict(source_run_ids),
                "play_key": play_key, "installation_id": installation_id,
                "workflow_id": workflow_id}
    if requested != expected:
        raise ValueError("Agent handoff unavailable")
    return {"agent_job_id": job_id, "agent_run_id": run_id,
            "authority": "advisory_only"}
