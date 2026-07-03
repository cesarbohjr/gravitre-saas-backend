/** Shared formatters for Intelligence Visibility Layer — no secrets, no chain-of-thought. */

import { humanizePlainEnglish } from "@/lib/plain-english"

export type ConfidenceBand = "high" | "medium" | "low" | "insufficient"

export function confidenceBand(score: number | null | undefined): ConfidenceBand {
  if (score == null || Number.isNaN(score)) return "insufficient"
  if (score >= 0.75) return "high"
  if (score >= 0.5) return "medium"
  return "low"
}

export function confidenceBandLabel(band: ConfidenceBand): string {
  switch (band) {
    case "high":
      return "High confidence"
    case "medium":
      return "Moderate confidence"
    case "low":
      return "Low confidence"
    default:
      return "Insufficient data"
  }
}

export function confidenceBandClass(band: ConfidenceBand): string {
  switch (band) {
    case "high":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
    case "medium":
      return "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
    case "low":
      return "border-rose-500/40 bg-rose-500/10 text-rose-900 dark:text-rose-200"
    default:
      return "border-border bg-muted/50 text-muted-foreground"
  }
}

export function formatMetric(value: number | null | undefined, suffix = ""): string {
  if (value == null || Number.isNaN(value)) return "—"
  return `${value}${suffix}`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  return `${Math.round(value * 100)}%`
}

export function formatScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  return value.toFixed(2)
}

export function readNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function readString(value: unknown, fallback = ""): string {
  if (value == null) return fallback
  return String(value)
}

/** Plain-English sentence from promotion audit decision_reasoning — never raw JSON. */
export function plainDecisionReasoning(value: unknown): string {
  return humanizePlainEnglish(
    value,
    "No reasoning recorded for this memory yet.",
  )
}

export function modelStatusChipClass(status: string): string {
  const normalized = status.toUpperCase()
  if (normalized === "TRAINED" || normalized === "READY") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
  }
  if (normalized === "PLANNED") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200"
  }
  return "border-border bg-muted/60 text-muted-foreground"
}

export function agentStatusBadgeClass(status: string): string {
  switch (status) {
    case "active":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
    case "degraded":
    case "error":
      return "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
    case "inactive":
    case "limited":
      return "border-border bg-muted/50 text-muted-foreground"
    default:
      return "border-sky-500/40 bg-sky-500/10 text-sky-900 dark:text-sky-200"
  }
}

export const DEPARTMENTS = [
  "marketing",
  "sales",
  "support",
  "operations",
  "finance",
  "hr",
  "engineering",
] as const

export type IntelligencePeriod = 7 | 30 | 90

export function periodLabel(days: IntelligencePeriod): string {
  return `${days}d`
}
