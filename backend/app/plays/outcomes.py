"""Typed Play business results on the existing intelligence outcome substrate.

Execution success and business success remain separate. This module never
upgrades provider acceptance or a completed workflow into VERIFIED SUCCESS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


PLAY_BUSINESS_RESULT_EVENT = "play_business_result"


class BusinessResultStatus(StrEnum):
    DETECTED = "DETECTED"
    RECOMMENDED = "RECOMMENDED"
    ACTIONED = "ACTIONED"
    PENDING_VERIFICATION = "PENDING VERIFICATION"
    VERIFIED_SUCCESS = "VERIFIED SUCCESS"
    VERIFIED_FAILURE = "VERIFIED FAILURE"
    INCONCLUSIVE = "INCONCLUSIVE"


class AttributionType(StrEnum):
    DIRECT = "direct"
    CORRELATIONAL = "correlational"
    ASSISTED = "assisted"
    NONE = "none"


@dataclass(frozen=True)
class SourceRecordRef:
    system: str
    record_type: str
    record_id: str


@dataclass(frozen=True)
class PlayBusinessResult:
    org_id: str
    play_key: str
    play_version: str
    outcome_type: str
    status: BusinessResultStatus
    metric_key: str | None = None
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    play_instance_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    agent_id: str | None = None
    connector_id: str | None = None
    baseline_value: float | None = None
    result_value: float | None = None
    unit: str | None = None
    currency: str | None = None
    confidence: float | None = None
    attribution_type: AttributionType = AttributionType.NONE
    attribution_weight: float | None = None
    source_records: tuple[SourceRecordRef, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    action_tools: tuple[str, ...] = ()
    verification_method: str | None = None
    occurred_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def delta_value(self) -> float | None:
        if self.baseline_value is None or self.result_value is None:
            return None
        return self.result_value - self.baseline_value

    @property
    def verified(self) -> bool:
        return self.status in {
            BusinessResultStatus.VERIFIED_SUCCESS,
            BusinessResultStatus.VERIFIED_FAILURE,
        }

    def validate(self) -> None:
        if not self.org_id or not self.play_key or not self.outcome_type:
            raise ValueError("org_id, play_key, and outcome_type are required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.attribution_weight is not None and not 0.0 <= self.attribution_weight <= 1.0:
            raise ValueError("attribution_weight must be between 0 and 1")
        if self.verified and not self.verification_method:
            raise ValueError("verified business results require verification_method")
        if self.status == BusinessResultStatus.VERIFIED_SUCCESS and not self.source_records:
            raise ValueError("VERIFIED SUCCESS requires at least one source-of-record reference")
        if self.currency and (self.unit or "").lower() not in {"currency", "money", "revenue"}:
            raise ValueError("currency is only valid for a monetary unit")

    def to_storage_row(self) -> dict[str, Any]:
        self.validate()
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            **dict(self.metadata or {}),
            "contract": "play_business_result/v1",
            "play_key": self.play_key,
            "play_version": self.play_version,
            "play_instance_id": self.play_instance_id,
            "outcome_type": self.outcome_type,
            "metric_key": self.metric_key,
            "delta_value": self.delta_value,
            "unit": self.unit,
            "currency": self.currency,
            "attribution_type": self.attribution_type.value,
            "attribution_weight": self.attribution_weight,
            "source_records": [asdict(ref) for ref in self.source_records],
            "evidence_ids": list(self.evidence_ids),
            "action_tools": list(self.action_tools),
            "verification_state": self.status.value,
            "verification_method": self.verification_method,
            "verified": self.verified,
            "occurred_at": self.occurred_at,
            "recorded_at": now,
        }
        return {
            "id": str(uuid4()),
            "org_id": self.org_id,
            "outcome_event": PLAY_BUSINESS_RESULT_EVENT,
            "entity_type": self.entity_type or "play",
            "entity_id": self.entity_id or self.play_instance_id or self.play_key,
            "workflow_id": self.workflow_id,
            "workflow_run_id": self.workflow_run_id,
            "agent_id": self.agent_id,
            "connector_id": self.connector_id,
            "confidence_score": self.confidence,
            "before_value": self.baseline_value,
            "after_value": self.result_value,
            "measured_at": self.occurred_at if self.verified else None,
            "measurement_status": (
                "recorded" if self.verified else self.status.value.lower().replace(" ", "_")
            ),
            "metadata": metadata,
            "created_at": now,
        }


def record_play_business_result(client: Any, result: PlayBusinessResult) -> dict[str, Any]:
    """Persist one validated result on the existing tenant outcome substrate."""
    row = result.to_storage_row()
    response = client.table("intelligence_outcome_events").insert(row).execute()
    data = response.data or []
    return dict(data[0]) if data else row


def list_play_business_results(
    client: Any,
    org_id: str,
    *,
    play_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read Play results only; all queries are explicitly org-scoped."""
    q = (
        client.table("intelligence_outcome_events")
        .select(
            "id, org_id, outcome_event, entity_type, entity_id, workflow_id, "
            "workflow_run_id, agent_id, connector_id, confidence_score, "
            "before_value, after_value, measured_at, measurement_status, metadata, created_at"
        )
        .eq("org_id", org_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 200)))
    )
    rows = list(q.execute().data or [])
    if play_key:
        wanted = play_key.strip().lower()
        rows = [
            row
            for row in rows
            if str((row.get("metadata") or {}).get("play_key") or "").strip().lower() == wanted
        ]
    return rows
