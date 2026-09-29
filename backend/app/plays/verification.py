"""Source-of-record verification bridge for Play business results.

This bridge is intentionally not exposed as a public mutation API. A caller
must already possess independently read source evidence. The bridge appends a
new verified/inconclusive event rather than mutating the ACTIONED event so the
outcome ledger stays auditable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.plays.outcomes import (
    AttributionType,
    BusinessResultStatus,
    PLAY_BUSINESS_RESULT_EVENT,
    PlayBusinessResult,
    SourceRecordRef,
    record_play_business_result,
)


@dataclass(frozen=True)
class SourceVerificationEvidence:
    system: str
    record_type: str
    record_id: str
    method: str
    observed_at: str
    baseline_value: float | None
    result_value: float | None
    outcome_type: str
    metric_key: str | None = None
    unit: str | None = None
    currency: str | None = None
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0

    def validate(self) -> None:
        if not self.system or not self.record_type or not self.record_id:
            raise ValueError("source verification requires source system, record type, and record id")
        if not self.method:
            raise ValueError("source verification requires a verification method")
        if not self.observed_at:
            raise ValueError("source verification requires observed_at")
        if self.result_value is None:
            raise ValueError("source verification requires a measured result value")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("source verification confidence must be between 0 and 1")


def _actioned_event(
    client: Any,
    org_id: str,
    actioned_outcome_id: str,
) -> dict[str, Any] | None:
    rows = (
        client.table("intelligence_outcome_events")
        .select(
            "id, org_id, outcome_event, entity_type, entity_id, workflow_id, "
            "workflow_run_id, agent_id, connector_id, metadata, created_at"
        )
        .eq("org_id", org_id)
        .eq("id", actioned_outcome_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    row = dict(rows[0])
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if str(metadata.get("verification_state") or "") != BusinessResultStatus.ACTIONED.value:
        return None
    return row


def record_source_verified_play_result(
    client: Any,
    *,
    org_id: str,
    actioned_outcome_id: str,
    evidence: SourceVerificationEvidence,
    success: bool,
    attribution_type: AttributionType = AttributionType.DIRECT,
    attribution_weight: float | None = 1.0,
) -> dict[str, Any]:
    """Append a verified result only from an existing ACTIONED Play event."""
    evidence.validate()
    actioned = _actioned_event(client, org_id, actioned_outcome_id)
    if actioned is None:
        raise ValueError("source verification requires an org-scoped ACTIONED Play result")

    metadata = actioned.get("metadata") if isinstance(actioned.get("metadata"), dict) else {}
    play_key = str(metadata.get("play_key") or "").strip()
    play_version = str(metadata.get("play_version") or "").strip()
    if not play_key or not play_version:
        raise ValueError("ACTIONED Play result is missing Play identity")

    if success:
        if not evidence.metric_key:
            raise ValueError("VERIFIED SUCCESS requires a measured metric_key")
        if evidence.baseline_value is None:
            raise ValueError("VERIFIED SUCCESS requires a baseline measurement")
        if evidence.outcome_type == "action_execution":
            raise ValueError("action execution verification is not business-result verification")

    source_ref = SourceRecordRef(
        system=evidence.system,
        record_type=evidence.record_type,
        record_id=evidence.record_id,
    )
    status = (
        BusinessResultStatus.VERIFIED_SUCCESS
        if success
        else BusinessResultStatus.VERIFIED_FAILURE
    )
    prior_evidence = tuple(str(v) for v in (metadata.get("evidence_ids") or []) if v)
    action_tools = tuple(str(v) for v in (metadata.get("action_tools") or []) if v)

    result = PlayBusinessResult(
        org_id=org_id,
        play_key=play_key,
        play_version=play_version,
        play_instance_id=metadata.get("play_instance_id"),
        outcome_type=evidence.outcome_type,
        status=status,
        metric_key=evidence.metric_key,
        workflow_id=actioned.get("workflow_id"),
        workflow_run_id=actioned.get("workflow_run_id"),
        entity_type=actioned.get("entity_type"),
        entity_id=actioned.get("entity_id"),
        agent_id=actioned.get("agent_id"),
        connector_id=actioned.get("connector_id"),
        baseline_value=evidence.baseline_value,
        result_value=evidence.result_value,
        unit=evidence.unit,
        currency=evidence.currency,
        confidence=evidence.confidence,
        attribution_type=attribution_type,
        attribution_weight=attribution_weight,
        source_records=(source_ref,),
        evidence_ids=tuple(dict.fromkeys((*prior_evidence, *evidence.evidence_ids))),
        action_tools=action_tools,
        verification_method=evidence.method,
        occurred_at=evidence.observed_at,
        metadata={
            "verified_from_actioned_outcome_id": actioned_outcome_id,
            "provider_acceptance_is_business_verification": False,
            "source_of_record_verified": True,
        },
    )
    return record_play_business_result(client, result)
