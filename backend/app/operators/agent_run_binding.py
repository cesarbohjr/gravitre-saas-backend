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
