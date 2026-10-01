"""Evidence drill-down for Play business results.

The drill-down joins only existing canonical records. Missing evidence stays
missing; this module never fabricates agent, approval, source-record, or
verification proof.
"""
from __future__ import annotations

from typing import Any

from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT


def _first(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    return dict(rows[0]) if rows else None


def get_play_business_result_event(
    client: Any,
    org_id: str,
    outcome_id: str,
    *,
    play_key: str | None = None,
) -> dict[str, Any] | None:
    rows = (
        client.table("intelligence_outcome_events")
        .select(
            "id, org_id, outcome_event, entity_type, entity_id, workflow_id, "
            "workflow_run_id, agent_id, connector_id, confidence_score, "
            "before_value, after_value, measured_at, measurement_status, metadata, created_at"
        )
        .eq("org_id", org_id)
        .eq("id", outcome_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .limit(1)
        .execute()
        .data
        or []
    )
    row = _first(rows)
    if row is None:
        return None
    if play_key:
        actual = str((row.get("metadata") or {}).get("play_key") or "").strip().lower()
        if actual != play_key.strip().lower():
            return None
    return row


def _workflow_run(client: Any, org_id: str, run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    rows = (
        client.table("workflow_runs")
        .select(
            "id, workflow_id, status, approval_status, required_approvals, "
            "created_at, completed_at, environment"
        )
        .eq("org_id", org_id)
        .eq("id", run_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return _first(rows)


def _approvals(client: Any, org_id: str, run_id: str | None) -> list[dict[str, Any]]:
    if not run_id:
        return []
    try:
        return list(
            (
                client.table("approvals")
                .select(
                    "id, run_id, title, type, priority, status, requested_by, "
                    "reviewed_by, requested_at, reviewed_at, numeric_value, "
                    "numeric_value_currency, numeric_value_label, context"
                )
                .eq("org_id", org_id)
                .eq("run_id", run_id)
                .order("requested_at", desc=False)
                .execute()
                .data
                or []
            )
        )
    except Exception:
        # Some older deployments may have only run_approvals. Read-only
        # evidence must degrade honestly rather than invent a gate record.
        return []


def build_play_evidence_chain(
    client: Any,
    org_id: str,
    outcome_id: str,
    *,
    play_key: str | None = None,
) -> dict[str, Any] | None:
    event = get_play_business_result_event(
        client,
        org_id,
        outcome_id,
        play_key=play_key,
    )
    if event is None:
        return None

    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    run_id = str(event.get("workflow_run_id") or "").strip() or None
    workflow = _workflow_run(client, org_id, run_id)
    approvals = _approvals(client, org_id, run_id)

    verification_state = str(metadata.get("verification_state") or "").strip() or None
    verification_method = str(metadata.get("verification_method") or "").strip() or None
    source_records = [
        row
        for row in (metadata.get("source_records") or [])
        if isinstance(row, dict)
    ]
    evidence_ids = [str(value) for value in (metadata.get("evidence_ids") or []) if value]
    actions = [str(value) for value in (metadata.get("action_tools") or []) if value]

    return {
        "outcomeId": str(event.get("id") or outcome_id),
        "metric": {
            "key": metadata.get("metric_key"),
            "baseline": event.get("before_value"),
            "result": event.get("after_value"),
            "delta": metadata.get("delta_value"),
            "unit": metadata.get("unit"),
            "currency": metadata.get("currency"),
            "measuredAt": event.get("measured_at"),
        },
        "entity": {
            "type": event.get("entity_type"),
            "id": event.get("entity_id"),
        },
        "play": {
            "key": metadata.get("play_key"),
            "version": metadata.get("play_version"),
            "instanceId": metadata.get("play_instance_id"),
            "runId": metadata.get("play_run_id") or metadata.get("run_id"),
            "installationId": metadata.get("installation_id"),
            "outcomeType": metadata.get("outcome_type"),
        },
        "workflow": {
            "id": event.get("workflow_id") or (workflow or {}).get("workflow_id"),
            "runId": run_id,
            "run": workflow,
        },
        "execution": {
            "agentId": event.get("agent_id"),
            "connectorId": event.get("connector_id"),
            "actions": actions,
        },
        "governance": {
            "approvals": approvals,
            "approvalStatus": (workflow or {}).get("approval_status"),
            "requiredApprovals": (workflow or {}).get("required_approvals"),
        },
        "sourceRecords": source_records,
        "evidenceIds": evidence_ids,
        "verification": {
            "state": verification_state,
            "method": verification_method,
            "verified": bool(metadata.get("verified")),
            "confidence": event.get("confidence_score"),
            "measurementStatus": event.get("measurement_status"),
        },
        "attribution": {
            "type": metadata.get("attribution_type"),
            "weight": metadata.get("attribution_weight"),
        },
        "truth": {
            "executionSuccessIsBusinessSuccess": False,
            "sourceOfRecordRequiredForVerifiedSuccess": True,
        },
    }
