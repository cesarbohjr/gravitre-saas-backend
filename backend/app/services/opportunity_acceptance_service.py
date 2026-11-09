"""Evidence-backed acceptance report for the canonical Play/workflow journey.

Inspects persisted tenant-owned Play, workflow, approval, step-verification and
delayed outcome rows. It does not execute, approve, or create an alternative
workflow/runtime. Synthetic tests do NOT substitute for provider consent or
live source-of-record certification.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.workflows.repository import get_run_with_steps


class AcceptanceEvidenceBlocked(ValueError):
    pass


def _timestamp(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if result.tzinfo is not None and result.utcoffset() is not None:
            return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def inspect_opportunity_play_run(
    *,
    client: Any, org_id: str, environment_name: str, play_run_id: str,
) -> dict[str, Any] | None:
    """Return a conservative acceptance state from independent persisted facts.

    A completed Play alone is insufficient. Each material external action must
    have a source-of-record verifier receipt, and a business outcome requires
    a separate before/after observation from the outcome attribution store.
    The result can be PARTIAL even if individual workflow rows say completed.
    """
    if not all((org_id, environment_name, play_run_id)):
        raise AcceptanceEvidenceBlocked("authenticated_play_run_required")
    rows = (
        client.table("play_runs").select("*")
        .eq("id", play_run_id).eq("org_id", org_id).limit(1).execute().data or []
    )
    if not rows:
        return None
    play = rows[0]
    if play.get("org_id") != org_id:
        raise AcceptanceEvidenceBlocked("cross_tenant_play_run")
    installation_id = str(play.get("installation_id") or "")
    install_rows = (
        client.table("play_installations").select("*")
        .eq("id", installation_id).eq("org_id", org_id)
        .eq("environment_name", environment_name).limit(1).execute().data or []
    )
    if not install_rows or install_rows[0].get("play_key") != play.get("play_key"):
        return None
    recorded_ids = play.get("workflow_run_ids")
    if not isinstance(recorded_ids, list) or not recorded_ids:
        return {
            "status": "NO_CANONICAL_WORKFLOW_RUNS", "playRunId": play_run_id,
            "businessOutcome": "NOT_MEASURED", "certified": False, "workflowRuns": [],
        }
    if len(set(map(str, recorded_ids))) != len(recorded_ids):
        raise AcceptanceEvidenceBlocked("duplicate_workflow_run_identity")

    runs: list[dict[str, Any]] = []
    all_approved = True
    all_verified = True
    all_completed = True
    all_measured = True
    for run_id_value in recorded_ids:
        run_id = str(run_id_value or "")
        run = get_run_with_steps(client, org_id, run_id, environment_name)
        if run is None or run.get("org_id") != org_id or run.get("environment") != environment_name:
            raise AcceptanceEvidenceBlocked("missing_or_cross_environment_workflow_run")
        params = run.get("parameters") or {}
        play_params = params.get("play") if isinstance(params, dict) else None
        if not isinstance(play_params, dict) or (
            str(play_params.get("run_id") or "") != play_run_id
            or str(play_params.get("installation_id") or "") != installation_id
            or play_params.get("key") != play.get("play_key")
            or play_params.get("execution_authority") != "canonical_workflow_runtime"
        ):
            raise AcceptanceEvidenceBlocked("unbound_canonical_play_run")
        approval_required = int(run.get("required_approvals") or 0)
        # This gate covers ACT WITH APPROVAL only. Mode and approval are read
        # from persisted records, never from model-suggested workflow metadata.
        if play.get("operating_mode") != "ACT WITH APPROVAL" or approval_required < 1:
            raise AcceptanceEvidenceBlocked("human_approval_gate_missing")
        approvals = (
            client.table("run_approvals").select("approver_id,status")
            .eq("run_id", run_id).eq("org_id", org_id).execute().data or []
        )
        approvers = {
            str(a.get("approver_id")) for a in approvals
            if a.get("status") == "approved" and a.get("approver_id")
        }
        declined = any(a.get("status") == "rejected" for a in approvals)
        approved = len(approvers) >= approval_required and not declined
        all_approved = all_approved and approved

        step_records = run.get("steps") or []
        if not isinstance(step_records, list) or not step_records:
            all_verified = False
        verified_writes = []
        for step in step_records:
            if step.get("org_id") != org_id or str(step.get("run_id")) != run_id:
                raise AcceptanceEvidenceBlocked("cross_tenant_step")
            snapshot = step.get("output_snapshot")
            if not isinstance(snapshot, dict) or snapshot.get("simulated") is True:
                all_verified = False
                continue
            action = str(snapshot.get("invoke_action") or "")
            if not action:
                continue
            from app.services.outcome_verification import is_write_action
            if not is_write_action(action):
                continue
            evidence = snapshot.get("verification")
            if (
                step.get("status") != "completed"
                or not isinstance(evidence, dict)
                or evidence.get("verified") is not True
                or not str(evidence.get("method") or evidence.get("read_action") or "").strip()
                or not str(evidence.get("resource_id") or evidence.get("entity_id") or "").strip()
                or not _timestamp(evidence.get("verified_at"))
                or snapshot.get("outcome_verified") is not True
            ):
                all_verified = False
                continue
            verified_writes.append({
                "stepId": step.get("step_id"), "action": action,
                "resourceId": str(evidence.get("resource_id") or evidence.get("entity_id")),
                "method": evidence.get("method"), "verifiedAt": evidence["verified_at"],
            })
        # No verified external effect means that no causal business impact can
        # be attributed to this execution, even if read steps completed.
        if not verified_writes:
            all_verified = False
        completed = run.get("run_type") == "execute" and run.get("status") == "completed"
        all_completed = all_completed and completed

        outcome_rows = (
            client.table("agent_action_outcomes").select("*")
            .eq("workflow_run_id", run_id).eq("org_id", org_id).execute().data or []
        )
        observed_outcomes = []
        for row in outcome_rows:
            before, after = row.get("metric_value_before"), row.get("metric_value_after")
            measured_at = _timestamp(row.get("measured_at"))
            action_at = _timestamp(row.get("action_taken_at"))
            if not (measured_at and action_at and measured_at >= action_at):
                continue
            if type(before) not in (float, int) or type(after) not in (float, int):
                continue
            if not (math.isfinite(float(before)) and math.isfinite(float(after))):
                continue
            if not any(
                receipt["action"] == row.get("action_type")
                and receipt["resourceId"] == str(row.get("target_entity_id") or "")
                for receipt in verified_writes
            ):
                continue
            observed_outcomes.append({
                "metric": row.get("metric_name"), "entityId": row.get("target_entity_id"),
                "before": before, "after": after,
                "delta": float(after) - float(before),
                "measuredAt": measured_at.isoformat(),
                "interpretation": "OBSERVED_CORRELATION_NOT_CAUSAL",
            })
        measured = bool(observed_outcomes)
        all_measured = all_measured and measured
        runs.append({
            "runId": run_id, "status": run.get("status"), "approvalVerified": approved,
            "verifiedWrites": verified_writes, "observedOutcomes": observed_outcomes,
            "sourceReadbacksVerified": bool(verified_writes), "outcomeMeasured": measured,
        })
    # A complete evidence report is NOT a promise of positive business lift.
    certified = all_approved and all_completed and all_verified and all_measured
    return {
        "status": "OBSERVED_CHAIN_COMPLETE" if certified else "ACCEPTANCE_INCOMPLETE",
        "playRunId": play_run_id, "playKey": play.get("play_key"),
        "orgId": org_id, "environment": environment_name,
        "workflowRuns": runs,
        "humanApprovalVerified": all_approved,
        "executionVerified": all_completed,
        "independentWriteReadbackVerified": all_verified,
        "measurableOutcomeObserved": all_measured,
        "businessOutcome": "MEASURED_CORRELATIONAL_ONLY" if certified else "NOT_MEASURED",
        "causalAttribution": "NOT_ESTABLISHED",
        "certified": certified,
    }
