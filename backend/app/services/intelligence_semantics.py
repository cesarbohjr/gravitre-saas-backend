"""G1 — Canonical semantic definitions for Intelligence projection.

These labels are the contract between map, chat, lenses, and pages.
One term must not mean several different measurements.
"""
from __future__ import annotations

from typing import Final

# ACTIVE AGENT — roster/configured status permits work (agents + operators merge).
# RUNNING AGENT — currently participating in swarm/workflow execution.
# ACTIVE WORKFLOW — workflow run in executing state.
# ACTION — discrete tool/workflow/connector execution event in window.
# PREDICTION — scoped assertion about business object with evidence.
# LEARNING — persisted business understanding change (not model readiness, not TTFT).
# OUTCOME — observed result tied to objective/action/workflow.
# IMPROVEMENT — measured outcome change attributable per GIBE rules.

MODEL_BUSINESS_LABELS: Final[dict[str, str]] = {
    "intent_classifier": "Intent Understanding",
    "workflow_anomaly_detector": "Workflow Anomaly Detection",
    "workflow_duration_forecaster": "Workflow Duration Forecasting",
    "workflow_success_predictor": "Workflow Success Prediction",
    "retrieval_ranker": "Retrieval Quality",
    "query_clusterer": "Knowledge Gap Detection",
    "memory_promotion_scorer": "Memory Promotion Scoring",
    "retrieval_memory_learner": "Retrieval Memory Learning",
    "revenue_forecaster": "Revenue Forecasting",
    "churn_risk_scorer": "Customer Churn Risk",
    "cf_matrix_factorizer": "Collaborative Filtering",
    "sla_breach_predictor": "SLA Breach Risk",
    "deal_loss_scorer": "Deal Loss Risk",
    "capacity_forecaster": "Capacity Forecasting",
}


def model_business_label(technical_slug: str) -> str:
    slug = (technical_slug or "").strip()
    if not slug:
        return "Model"
    return MODEL_BUSINESS_LABELS.get(slug, slug.replace("_", " ").title())


LENS_NODE_EMPHASIS: Final[dict[str, set[str]]] = {
    "knows": {"core", "entity", "knowledge", "domain", "connector"},
    "learns": {"core", "learning", "model", "outcome", "memory"},
    "predicts": {"core", "prediction", "signal", "evidence", "objective", "domain"},
    "acts": {"core", "agent", "workflow", "action", "connector", "approval", "domain"},
    "improves": {"core", "outcome", "objective", "learning", "domain"},
}

LENS_EDGE_EMPHASIS: Final[dict[str, set[str]]] = {
    "knows": {"KNOWS", "RELATED_TO", "READ_FROM"},
    "learns": {"LEARNED_FROM", "IMPROVED", "CONTRIBUTED_TO"},
    "predicts": {"PREDICTS", "EVIDENCE_FOR", "AFFECTS"},
    "acts": {"EXECUTED", "ASSIGNED_TO", "USED_BY", "REQUIRES_APPROVAL"},
    "improves": {"PRODUCED", "IMPROVED", "LEARNED_FROM", "CONTRIBUTED_TO"},
}
