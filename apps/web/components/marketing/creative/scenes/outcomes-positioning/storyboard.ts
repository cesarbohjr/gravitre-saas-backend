/**
 * Phase 10 — Outcomes Positioning storyboard (illustrative, deterministic).
 * Traces collapse into revenue / retention / efficiency — no invented metrics.
 */

export const ILLUSTRATIVE_CONTEXT =
  "Verified run traces collapse into positioning categories — labels for where work lands, not invented dollar claims."

export const OUTCOME_CATEGORIES = [
  { id: "revenue", label: "Revenue" },
  { id: "retention", label: "Retention" },
  { id: "efficiency", label: "Efficiency" },
] as const

export type OutcomesPhase =
  | "quiet"
  | "traces"
  | "cluster"
  | "categories"
  | "evidence"
  | "honest"

export const PHASE_ORDER: OutcomesPhase[] = [
  "quiet",
  "traces",
  "cluster",
  "categories",
  "evidence",
  "honest",
]

export const PHASE_CAPTION: Record<OutcomesPhase, string> = {
  quiet: "Outcomes at rest — no metric theater.",
  traces: "Multiple run traces arrive from governed work.",
  cluster: "Traces cluster by what they actually changed.",
  categories: "Positioning categories light — revenue, retention, efficiency.",
  evidence: "Evidence marks attach — still categories, not invented numbers.",
  honest: "Illustrative positioning only — no invented metrics.",
}

export function nextPhase(phase: OutcomesPhase): OutcomesPhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isOutcomesPhase(value: string | null | undefined): value is OutcomesPhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

export function parseOutcomesStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): OutcomesPhase | null {
  if (!isOutcomesPhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

export function showTraces(phase: OutcomesPhase): boolean {
  return phase !== "quiet"
}

export function showCluster(phase: OutcomesPhase): boolean {
  return ["cluster", "categories", "evidence", "honest"].includes(phase)
}

export function showCategories(phase: OutcomesPhase): boolean {
  return ["categories", "evidence", "honest"].includes(phase)
}

export function showEvidence(phase: OutcomesPhase): boolean {
  return phase === "evidence" || phase === "honest"
}

/** Same collapse path continues through categories → evidence. */
export const OUTCOMES_COLLAPSE_PATH_ID = "path-outcomes-collapse"
