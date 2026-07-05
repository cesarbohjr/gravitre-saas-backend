import { formatPercent, readString } from "@/lib/intelligence/helpers"
import type { DomainHealthEntry } from "@/lib/intelligence/visibility-types"

export function healthLabelText(label: string | undefined): string {
  switch (readString(label).toLowerCase()) {
    case "healthy":
    case "strong":
      return "Healthy"
    case "developing":
    case "improving":
      return "Improving"
    case "needs_attention":
      return "Needs attention"
    case "insufficient_data":
      return "Insufficient data"
    default:
      return label ? label.replace(/_/g, " ") : "Unknown"
  }
}

export function healthLabelClass(label: string | undefined): string {
  switch (readString(label).toLowerCase()) {
    case "healthy":
    case "strong":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
    case "developing":
    case "improving":
      return "border-sky-500/40 bg-sky-500/10 text-sky-900 dark:text-sky-200"
    case "needs_attention":
      return "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
    default:
      return "border-border bg-muted/50 text-muted-foreground"
  }
}

export function learningLevelClass(level: string | undefined): string {
  switch (readString(level).toLowerCase()) {
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

export function learningLevelLabel(level: string | undefined): string {
  switch (readString(level).toLowerCase()) {
    case "high":
      return "High confidence"
    case "medium":
      return "Medium confidence"
    case "low":
      return "Low confidence"
    case "insufficient_data":
      return "Insufficient data"
    default:
      return level ? level.replace(/_/g, " ") : "Insufficient data"
  }
}

export function freshnessLabelText(value: string | undefined): string {
  switch (readString(value).toLowerCase()) {
    case "good":
    case "fresh":
      return "Good"
    case "mixed":
      return "Mixed"
    case "needs_attention":
    case "stale":
      return "Needs attention"
    default:
      return value ? value.replace(/_/g, " ") : "Unknown"
  }
}

export function formatHealthScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  return String(Math.round(value * 100))
}

export function scoreLabelText(label: string | undefined): string {
  switch (readString(label).toLowerCase()) {
    case "strong":
      return "Strong"
    case "healthy":
      return "Healthy"
    case "developing":
      return "Developing"
    case "needs_attention":
      return "Needs attention"
    case "insufficient_data":
      return "Insufficient data"
    default:
      return label ? label.replace(/_/g, " ") : "Insufficient data"
  }
}

export function filterDomainHealthForDepartment(
  domains: DomainHealthEntry[] | undefined,
  department: string | undefined,
): DomainHealthEntry | null {
  if (!domains?.length) return null
  const needle = readString(department).toLowerCase()
  if (!needle) return null
  return (
    domains.find((row) => readString(row.department).toLowerCase() === needle) ??
    domains.find((row) => readString(row.domain).toLowerCase().includes(needle)) ??
    null
  )
}

export function maturityLevelDescription(level: number | undefined): string {
  switch (level) {
    case 1:
      return "Connected"
    case 2:
      return "Learning"
    case 3:
      return "Adaptive"
    case 4:
      return "Optimizing"
    case 5:
      return "Autonomous Intelligence"
    default:
      return "Connected"
  }
}

export function formatRetrievalEffectiveness(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—"
  return formatPercent(Math.min(1, Math.max(0, value > 1 ? value - 1 : value)))
}
