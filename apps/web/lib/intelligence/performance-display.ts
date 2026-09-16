/**
 * I7 — Client helpers for outcome attribution paths and ROI honesty.
 */
import type { OutcomeAttributionPath, OutcomePathStep } from "@/lib/api"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"
import type { AgentRoiMetric, AgentRoiProvenance } from "@/types/api"

export const PERFORMANCE_VIEW_MODES = [
  { id: "impact", label: "Business impact" },
  { id: "efficiency", label: "Efficiency" },
  { id: "agents", label: "Agent performance" },
  { id: "cost", label: "Cost" },
  { id: "reliability", label: "Reliability" },
] as const

export type PerformanceViewMode = (typeof PERFORMANCE_VIEW_MODES)[number]["id"]

export function unknownStepCopy(step: OutcomePathStep): string {
  if (step.qualityNote) return qualityFlagToCopy(step.qualityNote)
  return qualityFlagToCopy("INSUFFICIENT_EVIDENCE")
}

export function pickPrimaryOutcomePath(
  paths: OutcomeAttributionPath[] | null | undefined,
): OutcomeAttributionPath | null {
  if (!paths?.length) return null
  return [...paths].sort((a, b) => b.presentStepCount - a.presentStepCount)[0] ?? null
}

export function roiMetricIsUnknown(metric: AgentRoiMetric | null | undefined): boolean {
  if (!metric) return true
  const provenance: AgentRoiProvenance | undefined = metric.provenance
  if (provenance === "not_configured" || provenance === "insufficient_data") return true
  return metric.value == null || metric.value === ""
}

export function roiMetricDisplay(metric: AgentRoiMetric | null | undefined): {
  value: string
  hint: string
  unknown: boolean
} {
  if (!metric || roiMetricIsUnknown(metric)) {
    const flag =
      metric?.provenance === "not_configured" ? "NOT_CONFIGURED" : "INSUFFICIENT_DATA"
    return { value: "—", hint: qualityFlagToCopy(flag), unknown: true }
  }
  const num = typeof metric.value === "number" ? metric.value : Number(metric.value)
  let value = String(metric.value)
  if (!Number.isNaN(num)) {
    if (metric.unit === "usd") {
      value = new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: num >= 100 ? 0 : 2,
      }).format(num)
    } else if (metric.unit === "hours") {
      value = `${num.toFixed(num >= 10 ? 1 : 2)} h`
    } else if (metric.unit === "x") {
      value = `${num.toFixed(2)}×`
    } else {
      value = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(num)
    }
  }
  const hint =
    metric.provenance === "estimate"
      ? "Estimate — not measured time-on-task"
      : metric.provenance === "measured"
        ? "Measured"
        : metric.provenance === "operational"
          ? "Operational count"
          : metric.note ?? ""
  return { value, hint, unknown: false }
}
