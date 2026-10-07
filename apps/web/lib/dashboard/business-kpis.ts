/**
 * Business KPIs on the home dashboard.
 *
 * Definitions come from GET /api/metrics/business/catalog (org_metric_definitions).
 * The static list below only mirrors the canonical platform keys so saved layouts
 * and templates render a label before the catalog loads. Values always come from
 * GET /api/metrics/business; a missing value is shown as unknown, never as 0.
 */

import type {
  BusinessMetricDefinition,
  BusinessMetricRange,
  BusinessMetricValue,
} from "@/lib/api"
import type { BusinessDepartmentId, BusinessMetricUnit, DashboardRange } from "./types"

export const BUSINESS_KPI_PREFIX = "business."

export function businessKpiId(metricKey: string): string {
  return `${BUSINESS_KPI_PREFIX}${metricKey}`
}

export function isBusinessKpiId(metricId: string): boolean {
  return metricId.startsWith(BUSINESS_KPI_PREFIX) && metricId.length > BUSINESS_KPI_PREFIX.length
}

export function businessMetricKeyFromId(metricId: string): string | null {
  return isBusinessKpiId(metricId) ? metricId.slice(BUSINESS_KPI_PREFIX.length) : null
}

export const BUSINESS_DEPARTMENTS: { id: BusinessDepartmentId; label: string }[] = [
  { id: "marketing", label: "Growth / marketing" },
  { id: "sales", label: "Sales" },
  { id: "customer_success", label: "Customer success" },
  { id: "support", label: "Support" },
  { id: "operations", label: "Operations" },
  { id: "finance", label: "Finance" },
  { id: "msp", label: "MSP / IT" },
  { id: "executive", label: "Executive" },
]

export function departmentLabel(id: string | null | undefined, catalog?: { id: string; label: string }[]): string {
  if (!id) return "Business"
  const fromCatalog = catalog?.find((d) => d.id === id)?.label
  if (fromCatalog) return fromCatalog
  return BUSINESS_DEPARTMENTS.find((d) => d.id === id)?.label ?? humanizeMetricKey(id)
}

export type StaticBusinessMetric = {
  metricKey: string
  label: string
  unit: BusinessMetricUnit
  departments: BusinessDepartmentId[]
  /** funnel = activity that leads to an outcome; operational = process health. */
  kind: "business" | "funnel" | "operational"
  direction: "up" | "down"
}

function m(
  metricKey: string,
  label: string,
  unit: BusinessMetricUnit,
  departments: BusinessDepartmentId[],
  kind: StaticBusinessMetric["kind"] = "business",
  direction: StaticBusinessMetric["direction"] = "up",
): StaticBusinessMetric {
  return { metricKey, label, unit, departments, kind, direction }
}

/**
 * Canonical platform metric keys (PLATFORM_METRIC_DEFAULTS). Labels and units here are a
 * fallback only; the catalog response wins once it loads.
 */
export const CANONICAL_BUSINESS_METRICS: StaticBusinessMetric[] = [
  // Growth / marketing and sales funnel
  m("accounts_discovered", "Accounts discovered", "count", ["marketing"], "funnel"),
  m("accounts_qualified", "Accounts qualified", "count", ["marketing", "sales"]),
  m("decision_makers_identified", "Decision-makers identified", "count", ["marketing", "sales"]),
  m("qualified_contacts", "Qualified contacts", "count", ["marketing", "sales"]),
  m("verified_crm_prospects", "Verified CRM prospects", "count", ["marketing", "sales"]),
  m("outreach_delivered", "Outreach delivered", "count", ["marketing"], "funnel"),
  m("replies", "Replies", "count", ["marketing", "sales"]),
  m("positive_replies", "Positive replies", "count", ["marketing", "sales"]),
  m("reply_rate", "Reply rate", "ratio", ["marketing"]),
  m("meetings_booked", "Meetings booked", "count", ["marketing", "sales"]),
  m("opportunities_created", "Opportunities created", "count", ["sales", "marketing"]),
  m("qualified_pipeline_value", "Qualified pipeline value", "currency", ["sales", "marketing", "executive"]),
  m("won_revenue", "Won revenue", "currency", ["sales", "executive"]),
  m("lead_to_meeting_conversion", "Lead to meeting conversion", "ratio", ["marketing", "sales"]),
  m("meeting_to_opportunity_conversion", "Meeting to opportunity conversion", "ratio", ["sales"]),
  m("opportunity_to_won_conversion", "Opportunity to won conversion", "ratio", ["sales"]),
  m("deals_won", "Deals won", "count", ["sales"]),
  m("cost_per_qualified_opportunity", "Cost per qualified opportunity", "credits", ["marketing", "sales"], "business", "down"),
  m("time_to_first_response", "Time to first response", "hours", ["marketing", "sales"], "business", "down"),
  m("mql", "Marketing qualified leads", "count", ["marketing"]),
  m("cac", "Customer acquisition cost", "currency", ["marketing", "finance"], "business", "down"),
  m("arr", "Annual recurring revenue", "currency", ["finance", "executive"]),
  // Support / MSP
  m("mtta", "Mean time to acknowledge", "minutes", ["support", "msp"], "business", "down"),
  m("mttr", "Mean time to resolve", "hours", ["support", "msp"], "business", "down"),
  m("sla_compliance", "SLA compliance", "percent", ["support", "msp", "executive"]),
  m("first_contact_resolution", "First contact resolution", "percent", ["support"]),
  m("backlog", "Ticket backlog", "count", ["support", "msp"], "business", "down"),
  m("reopen_rate", "Reopen rate", "ratio", ["support"], "business", "down"),
  m("repeat_issue_rate", "Repeat issue rate", "ratio", ["support", "msp"], "business", "down"),
  m("customer_update_latency", "Customer update latency", "hours", ["support", "msp"], "business", "down"),
  m("csat", "Customer satisfaction", "percent", ["support", "customer_success", "executive"]),
  m("stale_ticket_rate", "Stale ticket rate", "ratio", ["support"], "business", "down"),
  m("tickets_rescued", "Tickets rescued", "count", ["support", "msp"]),
  m("knowledge_gap_rate", "Knowledge gap rate", "ratio", ["support"], "business", "down"),
  m("prevented_incidents", "Prevented incidents", "count", ["msp"]),
  m("automation_rate", "Automation rate", "ratio", ["msp", "operations"], "operational"),
  // Customer success
  m("customer_health", "Customer health", "percent", ["customer_success"]),
  m("revenue_at_risk", "Revenue at risk", "currency", ["customer_success", "executive"], "business", "down"),
  m("churned_revenue", "Churned revenue", "currency", ["customer_success", "finance"], "business", "down"),
  m("renewals_won", "Renewals won", "count", ["customer_success"]),
  m("nrr", "Net revenue retention", "percent", ["customer_success", "executive"]),
  // Finance
  m("revenue_recovered", "Revenue recovered", "currency", ["finance", "executive"]),
  m("dso", "Days sales outstanding", "count", ["finance"], "business", "down"),
  m("cash_risk", "Cash at risk", "currency", ["finance"], "business", "down"),
  m("invoices_collected", "Invoices collected", "count", ["finance"]),
  // Operations
  m("policy_compliance", "Policy compliance", "percent", ["operations"]),
  m("exception_rate", "Exception rate", "ratio", ["operations"], "business", "down"),
  m("exception_resolution_time", "Exception resolution time", "hours", ["operations"], "business", "down"),
  m("auto_recovery_rate", "Auto-recovery rate", "ratio", ["operations"]),
  m("human_escalation_rate", "Human escalation rate", "ratio", ["operations"], "business", "down"),
  m("escalation_rate", "Escalation rate", "ratio", ["operations", "support"], "business", "down"),
]

export const CANONICAL_BUSINESS_METRIC_KEYS = new Set(CANONICAL_BUSINESS_METRICS.map((d) => d.metricKey))

export function humanizeMetricKey(key: string): string {
  const words = key.replace(/[_.-]+/g, " ").trim()
  if (!words) return "Business metric"
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** The business endpoints accept 7d | 30d | 90d; shorter dashboard ranges are served as 7 days. */
export function toApiRange(range: DashboardRange): BusinessMetricRange {
  if (range === "30d") return "30d"
  if (range === "90d") return "90d"
  return "7d"
}

export function businessEvidenceHref(metricKey: string, range?: BusinessMetricRange): string {
  const base = `/metrics/business/${encodeURIComponent(metricKey)}`
  return range ? `${base}?range=${range}` : base
}

function trimZero(text: string): string {
  return text.replace(/\.0(?=\D*$)/, "")
}

/** Format a verified value by unit. Callers must handle null themselves (unknown, never 0). */
export function formatBusinessValue(
  value: number,
  unit: BusinessMetricUnit | string | null | undefined,
  currency?: string | null,
): string {
  if (!Number.isFinite(value)) return "Unknown"
  switch (unit) {
    case "currency": {
      if (currency) {
        try {
          return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency,
            notation: Math.abs(value) >= 100_000 ? "compact" : "standard",
            maximumFractionDigits: Math.abs(value) >= 100_000 ? 1 : 0,
          }).format(value)
        } catch {
          return `${currency} ${Math.round(value).toLocaleString("en-US")}`
        }
      }
      return Math.round(value).toLocaleString("en-US")
    }
    case "ratio":
      return `${trimZero((value * 100).toFixed(1))}%`
    case "percent":
      return `${trimZero(value.toFixed(1))}%`
    case "hours":
      return `${trimZero(value.toFixed(1))} h`
    case "minutes":
      return `${Math.round(value).toLocaleString("en-US")} min`
    case "credits":
      return `${trimZero(value.toFixed(1))} credits`
    default:
      return Number.isInteger(value) ? value.toLocaleString("en-US") : trimZero(value.toFixed(1))
  }
}

export type BusinessValueDisplay = {
  /** Primary text: a formatted verified value, "Unknown", or "Not yet verified". */
  value: string
  /** Secondary text explaining the value or why it is unknown. */
  hint: string
  state: "verified" | "not_verified" | "unknown" | "loading"
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`
}

/** Turn an API value (or its absence) into honest display copy. Null is never rendered as 0. */
export function describeBusinessValue(
  metric: BusinessMetricValue | null | undefined,
  opts: { loading?: boolean; failed?: boolean } = {},
): BusinessValueDisplay {
  if (!metric) {
    if (opts.loading) return { value: "—", hint: "Checking verified results", state: "loading" }
    if (opts.failed) {
      return { value: "Unknown", hint: "Gravitre could not load this metric right now.", state: "unknown" }
    }
    return { value: "Unknown", hint: "This metric is not set up for your workspace yet.", state: "unknown" }
  }
  if (metric.status === "verified" && typeof metric.value === "number" && Number.isFinite(metric.value)) {
    const parts = [plural(metric.verifiedResultCount, "verified result")]
    if (metric.assistedResultCount > 0) parts.push(`${metric.assistedResultCount} assisted`)
    return {
      value: formatBusinessValue(metric.value, metric.unit, metric.currency),
      hint: parts.join(" · "),
      state: "verified",
    }
  }
  if (metric.status === "no_verified_evidence") {
    return {
      value: "Not yet verified",
      hint: metric.reason?.trim() || "No result has been confirmed in the source system yet.",
      state: "not_verified",
    }
  }
  if (metric.status === "not_defined") {
    return {
      value: "Unknown",
      hint: metric.reason?.trim() || "This metric is not set up for your workspace yet.",
      state: "unknown",
    }
  }
  return {
    value: "Unknown",
    hint: metric.reason?.trim() || "Not enough verified data to calculate this yet.",
    state: "unknown",
  }
}

export function definitionDepartments(def: Pick<BusinessMetricDefinition, "department" | "departments">): string[] {
  const all = [def.department, ...(def.departments ?? [])].filter((d): d is string => Boolean(d))
  return [...new Set(all)]
}
