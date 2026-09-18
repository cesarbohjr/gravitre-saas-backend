"""2.0-G multi-source diagnostic — why pipeline / AR / support, no invented cause."""
from __future__ import annotations

from app.services.execution_plan_service import ExecutionObservation, reconcile_execution_plan
from app.services.multi_source_diagnostic import (
    INSUFFICIENT_EVIDENCE,
    conclude_diagnostic,
    match_diagnostic_recipe,
)


def test_why_pipeline_matches_recipe() -> None:
    assert match_diagnostic_recipe("Why did the pipeline fall this week?") == "sales.pipeline.health"
    assert match_diagnostic_recipe("How is the weather") is None


def test_why_pipeline_golden_plan_has_hypothesis_and_evidence() -> None:
    plan = reconcile_execution_plan(
        message="Why did our pipeline fall this week?",
        task_state={},
        connected_integrations=["hubspot", "google_analytics"],
    )
    assert plan.source == "multi_source_diagnostic"
    kinds = [s.kind for s in plan.steps]
    assert "hypothesis" in kinds
    assert "evidence" in kinds
    assert "compose" in kinds
    assert any(s.action_key for s in plan.steps if s.kind == "evidence")


def test_why_pipeline_insufficient_evidence_honesty() -> None:
    plan = reconcile_execution_plan(
        message="Why did the pipeline drop?",
        task_state={},
        connected_integrations=["hubspot"],
    )
    verdict = conclude_diagnostic(plan, [])
    assert verdict["sufficient"] is False
    assert verdict["message"] == INSUFFICIENT_EVIDENCE
    assert "guess" in verdict["message"].lower()


def test_why_pipeline_observed_only_not_causal() -> None:
    plan = reconcile_execution_plan(
        message="Why did the pipeline drop?",
        task_state={},
        connected_integrations=["hubspot"],
    )
    evidence = next(s for s in plan.steps if s.kind == "evidence")
    verdict = conclude_diagnostic(
        plan,
        [
            ExecutionObservation(
                step_id=evidence.step_id,
                connector_id="hubspot",
                success=True,
                summary="12 open deals, $40k",
            )
        ],
    )
    assert verdict["sufficient"] is True
    assert "not a causal explanation" in verdict["message"]
    assert "12 open deals" in verdict["message"]


def test_ar_and_support_diagnostics() -> None:
    assert match_diagnostic_recipe("why are invoices overdue") == "finance.receivables.overdue"
    assert match_diagnostic_recipe("why did support tickets spike") == "support.issue_trends"
    ar = reconcile_execution_plan(
        message="Why are receivables overdue?",
        task_state={},
        connected_integrations=["quickbooks"],
    )
    assert ar.capability_id == "finance.receivables.overdue"
