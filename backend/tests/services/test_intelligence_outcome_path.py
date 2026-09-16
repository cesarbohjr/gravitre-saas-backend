"""I7 — Outcome attribution path builder uses snapshot evidence only."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.intelligence_projection import (
    CanonicalAgent,
    CanonicalPrediction,
    IntelligenceMetrics,
    IntelligenceProvenance,
    IntelligenceSnapshot,
    LearningInsight,
)
from app.services.intelligence_outcome_path import OUTCOME_PATH_STEP_KINDS, build_outcome_paths


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prov() -> IntelligenceProvenance:
    return IntelligenceProvenance(system="test", recordId="r1", fetchedAt=_now())


def test_outcome_path_has_full_chain_and_unknown_gaps():
    snapshot = IntelligenceSnapshot(
        generatedAt=_now(),
        tenantId="org-i7",
        timeWindowHours=24,
        coreState="idle",
        agents=[],
        metrics=IntelligenceMetrics(outcomes={"measuredOutcomes": 0}),
        departments=[{"id": "sales", "recentResolved": 0}],
        outcomes=[],
    )
    paths = build_outcome_paths(snapshot)
    assert len(paths) == 1
    assert [step.kind for step in paths[0].steps] == list(OUTCOME_PATH_STEP_KINDS)
    assert paths[0].steps[0].present is True
    assert paths[0].steps[0].label == "Sales"
    missing = [step for step in paths[0].steps if not step.present]
    assert missing
    assert all(step.qualityNote == "INSUFFICIENT_EVIDENCE" for step in missing)
    assert all(step.evidence == [] for step in missing)


def test_outcome_path_fills_steps_from_real_snapshot_rows():
    now = _now()
    snapshot = IntelligenceSnapshot(
        generatedAt=now,
        tenantId="org-i7",
        timeWindowHours=24,
        coreState="flow-inward",
        agents=[
            CanonicalAgent(
                id="agt-1",
                name="Sales Closer",
                department="sales",
                businessLabel="Sales Closer",
                configuredStatus="active",
                executionStatus="idle",
                isConfiguredActive=True,
                isCurrentlyRunning=False,
                source=_prov(),
            )
        ],
        predictions=[
            CanonicalPrediction(
                id="p1",
                type="risk",
                businessStatement="Deal slip risk in enterprise",
                department="sales",
                evidence=["3 stalled deals"],
                source=_prov(),
                semanticKey="sk1",
            )
        ],
        learnings=[
            LearningInsight(
                id="l1",
                businessStatement="Multi-thread enterprise deals close faster",
                learnedFrom=["memory_promotion"],
                evidence=["3 won deals"],
                source=_prov(),
            )
        ],
        metrics=IntelligenceMetrics(outcomes={"measuredOutcomes": 2}),
        departments=[{"id": "sales", "recentResolved": 2}],
        signals=[{"id": "s1", "title": "Enterprise pipeline stall", "department": "sales", "summary": "Aging deals"}],
        outcomes=[
            {
                "id": "e1",
                "event": "recommendation_created",
                "department": "sales",
                "createdAt": now,
            },
            {
                "id": "e2",
                "event": "connector_action_executed",
                "department": "sales",
                "agentId": "agt-1",
                "createdAt": now,
            },
            {
                "id": "e3",
                "event": "business_metric_improved",
                "department": "sales",
                "createdAt": now,
            },
        ],
    )
    path = build_outcome_paths(snapshot)[0]
    by_kind = {step.kind: step for step in path.steps}
    assert by_kind["signal"].present is True
    assert "pipeline stall" in by_kind["signal"].label.lower()
    assert by_kind["prediction"].present is True
    assert by_kind["agent_workflow"].label == "Sales Closer"
    assert by_kind["action"].present is True
    assert by_kind["outcome"].present is True
    assert by_kind["business_impact"].present is True
    assert "2 measured" in by_kind["business_impact"].label
    assert by_kind["learning"].present is True
    assert path.complete is True


def test_unknown_steps_do_not_invent_dollar_impact():
    snapshot = IntelligenceSnapshot(
        generatedAt=_now(),
        tenantId="org-i7",
        timeWindowHours=24,
        coreState="idle",
        metrics=IntelligenceMetrics(outcomes={"measuredOutcomes": 0}),
        departments=[{"id": "finance", "recentResolved": 0}],
    )
    path = build_outcome_paths(snapshot)[0]
    impact = next(step for step in path.steps if step.kind == "business_impact")
    assert impact.present is False
    assert "$" not in impact.label
