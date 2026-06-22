/**
 * STA-286: transparent labeling for estimate vs operational outcome metrics.
 * Ground-truth time-on-task measurement is deferred (STA-289).
 */

export type OutcomeMeasurementKind = "estimate" | "operational"

/** Catalog / publisher-provided hours-saved (not measured time-on-task). */
export const ESTIMATED_HOURS_SAVED_LABEL = "Estimated hours saved"
export const ESTIMATED_HOURS_SAVED_MONTHLY = "Est. hours saved / month"
export const ADOPTED_ESTIMATE_HOURS_LABEL = "Estimated hours (adopted)"
export const CATALOG_ESTIMATE_HOURS_LABEL = "Estimated hours (catalog)"
export const ADOPTION_RATE_ESTIMATE_LABEL = "Adoption rate (estimates)"
export const ROI_PAGE_TITLE = "Estimated hours saved (ROI)"

export const ROI_METHODOLOGY =
  "Hours saved are catalog estimates (time per manual task × automated volume), not measured time-on-task. Adopted estimates count when an install records at least one usage event."

/** Optimization / suggestion impact strings (heuristic, not measured). */
export const ESTIMATED_IMPACT_LABEL = "Estimated impact"
export const OPTIMIZATION_ESTIMATE_METHODOLOGY =
  "Impact ranges come from run telemetry and heuristics, not controlled before/after time-on-task studies."

/** Counts from agent jobs, workflow runs, and audit events in Gravitre. */
export const OPERATIONAL_TASKS_COMPLETED_LABEL = "Tasks completed (operational)"
export const OPERATIONAL_TASKS_FAILED_LABEL = "Tasks failed (operational)"
export const OPERATIONAL_TASKS_RUNNING_LABEL = "Tasks running (operational)"
export const OPERATIONAL_SUCCESS_RATE_LABEL = "Success rate (operational)"
export const OPERATIONAL_METHODOLOGY =
  "Counts completed jobs, runs, and tool events recorded in Gravitre. Operational telemetry — not measured business time-on-task or hours saved."

export const OPERATIONAL_METHODOLOGY_SHORT =
  "Operational counts from system records — not measured hours saved."

export const OUTCOME_LABELING_DOC_PATH = "docs/ai/OUTCOME_ESTIMATE_LABELING.md"

export const OUTCOME_LABELING_SUMMARY =
  "Estimate metrics (hours saved, ROI, optimization impact) are modeled or catalog-based until STA-289 ground-truth measurement ships. Operational counts reflect recorded executions only."
