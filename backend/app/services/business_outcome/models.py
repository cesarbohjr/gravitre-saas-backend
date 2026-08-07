"""BusinessOutcome — customer-facing projection of Module A's canonical record.

Hard rules:
- Read-only DTO. Nothing writes a BusinessOutcome; it is always derived.
- Sections are omitted when empty — never fabricated.
- Lifecycle states must map to real triggers (see projector).
- Frontend must not reinterpret business data; this DTO is render-ready.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

BusinessOutcomeKind = Literal[
    "created_record",
    "found_existing_record",
    "updated_record",
    "failed_action",
    "completed_workflow",
    "completed_swarm",
    "generated_report",
    "recommendation",
    "research_finding",
    "approval",
    "other",
]

# Only states with real triggers may appear (Phase 0 grounding).
LifecycleState = Literal[
    "created",
    "verified",
    "presented",
    "approved",
    "undone",
]

PipelineStage = Literal[
    "verify",
    "normalize",
    "business_outcome",
    "memory",
    "recommendation",
    "notification",
]


@dataclass
class OutcomeLink:
    label: str
    href: str
    kind: Literal["gravitre", "vendor", "audit", "other"] = "other"


@dataclass
class EvidenceSection:
    links: list[OutcomeLink] = field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None
    integration: str | None = None


@dataclass
class VerificationSection:
    verified: bool
    method: str
    detail: str | None = None
    # Phase 6 — honest review state (Phase 3 follow-up vs Phase 4 degeneracy).
    review_state: str | None = None  # e.g. flagged_for_review
    check_failed: str | None = None  # batch_degeneracy | follow_up_proof | effect_unproven
    finding: str | None = None
    next_actions: list[str] | None = None


@dataclass
class TimelineStep:
    index: int
    label: str
    status: str
    summary: str | None = None
    evidence_url: str | None = None
    agent_name: str | None = None


@dataclass
class ApprovalSection:
    status: str
    required: int | None = None
    received: int | None = None


@dataclass
class RecommendationSection:
    title: str
    reason: str
    suggested_utterance: str | None = None
    advisory_only: bool = True
    href: str | None = None
    confidence: float | None = None
    confidence_is_estimate: bool = True


@dataclass
class DiffSection:
    available: bool
    prior: dict[str, Any] | None = None
    note: str | None = None


@dataclass
class UndoSection:
    available: bool
    compensating_action: str | None = None
    honest_unavailable_reason: str | None = None


@dataclass
class BusinessOutcomeSections:
    summary: str | None = None
    impact: str | None = None  # Always omit until real impact data exists
    evidence: EvidenceSection | None = None
    verification: VerificationSection | None = None
    explanation: str | None = None
    timeline: list[TimelineStep] | None = None
    related_outcomes: list[str] | None = None  # Always omit until real edges
    dependencies: list[str] | None = None  # Always omit until joined
    recommendations: list[RecommendationSection] | None = None
    history: list[dict[str, Any]] | None = None  # Always omit until versioning
    approval: ApprovalSection | None = None
    diff: DiffSection | None = None
    undo: UndoSection | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class BusinessOutcome:
    """Canonical customer-facing outcome. One shape for every consumer."""

    id: str
    org_id: str
    kind: BusinessOutcomeKind
    title: str
    status: str
    lifecycle_state: LifecycleState
    lifecycle_states_reached: list[LifecycleState]
    source: str | None
    created_at: str | None
    sections: BusinessOutcomeSections
    pipeline_stages_completed: list[PipelineStage] = field(default_factory=list)
    module_a_schema_version: str | None = None
    run_id: str | None = None
    conversation_id: str | None = None
    # Explicit: consumers must not display raw Module A — only this DTO.
    projection: str = "business_outcome"
    advisory_only_recommendations: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Render-ready JSON. Omits empty optional sections."""
        sections = _sections_to_dict(self.sections)
        return {
            "id": self.id,
            "orgId": self.org_id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "lifecycleState": self.lifecycle_state,
            "lifecycleStatesReached": list(self.lifecycle_states_reached),
            "source": self.source,
            "createdAt": self.created_at,
            "sections": sections,
            "pipelineStagesCompleted": list(self.pipeline_stages_completed),
            "moduleASchemaVersion": self.module_a_schema_version,
            "runId": self.run_id,
            "conversationId": self.conversation_id,
            "projection": self.projection,
            "advisoryOnlyRecommendations": self.advisory_only_recommendations,
        }


def _sections_to_dict(sections: BusinessOutcomeSections) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if sections.summary:
        out["summary"] = sections.summary
    # impact intentionally never fabricated
    if sections.evidence and (sections.evidence.links or sections.evidence.entity_id):
        out["evidence"] = {
            "links": [asdict(link) for link in sections.evidence.links],
            "entityType": sections.evidence.entity_type,
            "entityId": sections.evidence.entity_id,
            "integration": sections.evidence.integration,
        }
    if sections.verification is not None:
        ver = sections.verification
        verification: dict[str, Any] = {
            "verified": ver.verified,
            "method": ver.method,
        }
        if ver.detail:
            verification["detail"] = ver.detail
        if ver.review_state:
            verification["reviewState"] = ver.review_state
        if ver.check_failed:
            verification["checkFailed"] = ver.check_failed
        if ver.finding:
            verification["finding"] = ver.finding
        if ver.next_actions:
            verification["nextActions"] = list(ver.next_actions)
        out["verification"] = verification
    if sections.explanation:
        out["explanation"] = sections.explanation
    if sections.timeline:
        out["timeline"] = [
            {
                "index": step.index,
                "label": step.label,
                "status": step.status,
                "summary": step.summary,
                "evidenceUrl": step.evidence_url,
                "agentName": step.agent_name,
            }
            for step in sections.timeline
        ]
    if sections.recommendations:
        out["recommendations"] = [
            {
                "title": rec.title,
                "reason": rec.reason,
                "suggestedUtterance": rec.suggested_utterance,
                "advisoryOnly": True,
                "href": rec.href,
                "confidence": rec.confidence,
                "confidenceIsEstimate": rec.confidence_is_estimate,
            }
            for rec in sections.recommendations
        ]
    if sections.approval is not None:
        out["approval"] = asdict(sections.approval)
    if sections.diff is not None:
        out["diff"] = {
            "available": sections.diff.available,
            "prior": sections.diff.prior,
            "note": sections.diff.note,
        }
    if sections.undo is not None:
        out["undo"] = {
            "available": sections.undo.available,
            "compensatingAction": sections.undo.compensating_action,
            "honestUnavailableReason": sections.undo.honest_unavailable_reason,
        }
    if sections.metadata:
        out["metadata"] = dict(sections.metadata)
    return out
