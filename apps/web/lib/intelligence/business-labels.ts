/**
 * G6 — Business-facing labels mirrored from backend intelligence_semantics.py.
 * Never show raw model slugs on customer intelligence surfaces.
 */
export const MODEL_BUSINESS_LABELS: Record<string, string> = {
  intent_classifier: "Intent Understanding",
  workflow_anomaly_detector: "Workflow Anomaly Detection",
  workflow_duration_forecaster: "Workflow Duration Forecasting",
  workflow_success_predictor: "Workflow Success Prediction",
  retrieval_ranker: "Retrieval Quality",
  query_clusterer: "Knowledge Gap Detection",
  memory_promotion_scorer: "Memory Promotion Scoring",
  retrieval_memory_learner: "Retrieval Memory Learning",
  revenue_forecaster: "Revenue Forecasting",
  churn_risk_scorer: "Customer Churn Risk",
  cf_matrix_factorizer: "Collaborative Filtering",
  sla_breach_predictor: "SLA Breach Risk",
  deal_loss_scorer: "Deal Loss Risk",
  capacity_forecaster: "Capacity Forecasting",
}

export function modelBusinessLabel(technicalSlug: string | null | undefined): string {
  const slug = (technicalSlug ?? "").trim()
  if (!slug) return "Model"
  return MODEL_BUSINESS_LABELS[slug] ?? slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
