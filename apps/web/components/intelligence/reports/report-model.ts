/**
 * Reports v2 — pure builders that turn real Gravitre payloads into the
 * design's stat cards and evidence trail. Nothing here invents a value:
 * when a source has no data the card says so ("—" / No evidence).
 */
import type { IntelligencePageContextResponse, OutcomeAttributionPath, OutcomePathStep } from "@/lib/api"
import type { ReportTemplateId } from "@/lib/intelligence/saved-intelligence-views"
import { readNumber } from "@/lib/intelligence/helpers"
import { formatPredictions } from "@/lib/intelligence/prediction-display"
import { roiMetricDisplay, roiMetricIsUnknown } from "@/lib/intelligence/performance-display"
import type { AgentRoiMetric, AgentRoiReport, Connector } from "@/types/api"

export type ReportPeriodDays = 7 | 30 | 90

export const REPORT_PERIODS: ReadonlyArray<{ days: ReportPeriodDays; label: string }> = [
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
]

export const TEMPLATE_BLURBS: Record<ReportTemplateId, string> = {
  business: "What changed for the business, and how much of it Gravitre can prove.",
  agent: "What your agents did and what they cost.",
  prediction: "What Gravitre expects next, and how often it has been right.",
  governance: "Who approved what, and what is waiting on a person.",
}

export type KpiEvidence = "measured" | "estimated" | "none"

export type ReportKpi = {
  label: string
  value: string
  note: string
  evidence: KpiEvidence
}

const LOADING_NOTE = "Loading…"

function pending(label: string): ReportKpi {
  return { label, value: "—", note: LOADING_NOTE, evidence: "none" }
}

function evidenceFromRoi(metric: AgentRoiMetric | null | undefined): KpiEvidence {
  if (!metric || roiMetricIsUnknown(metric)) return "none"
  if (metric.provenance === "estimate" || metric.provenance === "org_settings") return "estimated"
  return "measured"
}

function roiKpi(label: string, metric: AgentRoiMetric | null | undefined, note: string, emptyNote: string): ReportKpi {
  const display = roiMetricDisplay(metric)
  const evidence = evidenceFromRoi(metric)
  return {
    label,
    value: display.value,
    note: evidence === "none" ? emptyNote : note,
    evidence,
  }
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

/** The seven design steps; the backend's eighth "learning" step is not part of this trail. */
export const TRAIL_STEP_KINDS = [
  "objective",
  "signal",
  "prediction",
  "agent_workflow",
  "action",
  "outcome",
  "business_impact",
] as const

export type TrailStepKind = (typeof TRAIL_STEP_KINDS)[number]

export const TRAIL_STEP_LABEL: Record<TrailStepKind, string> = {
  objective: "Objective",
  signal: "Signal",
  prediction: "Prediction",
  agent_workflow: "Agent",
  action: "Action",
  outcome: "Outcome",
  business_impact: "Business impact",
}

/** Which Gravitre record each step is read from (see backend intelligence_outcome_path.py). */
export const TRAIL_STEP_SOURCE: Record<TrailStepKind, string> = {
  objective: "Objective scope",
  signal: "Business signals",
  prediction: "Forecasts",
  agent_workflow: "Agents",
  action: "Activity log",
  outcome: "Outcome events",
  business_impact: "Impact",
}

export const TRAIL_STEP_MISSING_TEXT: Record<TrailStepKind, string> = {
  objective: "No objective covers this part of the business yet.",
  signal: "No business signal has been recorded here yet.",
  prediction: "Gravitre has not forecast anything for this yet.",
  agent_workflow: "No agent or workflow has picked this up yet.",
  action: "No action has been taken on this yet.",
  outcome: "There is no verified result yet.",
  business_impact: "No money or time value is attached yet.",
}

export const TRAIL_STEP_FILL: Record<TrailStepKind, string> = {
  objective: "This fills in when an objective is set for this part of the business.",
  signal: "This fills in when a connected source reports a business signal.",
  prediction: "This fills in when Gravitre forecasts what happens next.",
  agent_workflow: "This fills in when an agent or workflow acts on the prediction.",
  action: "Approving a suggested fix in Forecasts, or an agent action, records the action here.",
  outcome: "When the next run finishes, Gravitre records whether it succeeded.",
  business_impact: "Turn on revenue tracking in Impact so outcomes like this can carry a value.",
}

export const TRAIL_STEP_CONTINUES: Record<TrailStepKind, string> = {
  objective: "an objective covers this scope",
  signal: "a connected source reports a signal",
  prediction: "Gravitre forecasts what happens next",
  agent_workflow: "an agent acts on this prediction",
  action: "an action is taken",
  outcome: "a verified result is recorded",
  business_impact: "revenue tracking attaches a value",
}

export type TrailStep = {
  n: number
  kind: TrailStepKind
  label: string
  present: boolean
  proof: string[]
  sourceRecordId: string | null
  recordedAt: string | null
  from: string | null
}

const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/

export function toTrailSteps(path: OutcomeAttributionPath | null | undefined): TrailStep[] {
  if (!path) return []
  const byKind = new Map<string, OutcomePathStep>()
  for (const step of path.steps) byKind.set(step.kind, step)
  return TRAIL_STEP_KINDS.map((kind, index) => {
    const step = byKind.get(kind)
    const present = Boolean(step?.present)
    const evidence = (step?.evidence ?? []).map((line) => line.trim()).filter(Boolean)
    const recorded = evidence.find((line) => TIMESTAMP_RE.test(line)) ?? null
    // Raw linked-record ids and timestamps are shown in the source record block, not as proof.
    const proof = evidence.filter((line) => !TIMESTAMP_RE.test(line) && !/^linked record /i.test(line))
    return {
      n: index + 1,
      kind,
      label: present ? (step?.label?.trim() || TRAIL_STEP_LABEL[kind]) : "Not yet",
      present,
      proof,
      sourceRecordId: present ? (step?.sourceRecordId?.trim() || null) : null,
      recordedAt: present ? recorded : null,
      from: present ? TRAIL_STEP_SOURCE[kind] : null,
    }
  })
}

/** Path with the most evidence (ties keep backend order). */
export function pickTrailPath(paths: OutcomeAttributionPath[] | null | undefined): OutcomeAttributionPath | null {
  if (!paths?.length) return null
  let best: OutcomeAttributionPath | null = null
  let bestCount = -1
  for (const path of paths) {
    const count = toTrailSteps(path).filter((s) => s.present).length
    if (count > bestCount) {
      best = path
      bestCount = count
    }
  }
  return best
}

/** Latest step with evidence, so the trail headline names the furthest point Gravitre can prove. */
export function trailHeadline(steps: TrailStep[], path: OutcomeAttributionPath | null): string | null {
  const lastPresent = [...steps].reverse().find((s) => s.present && s.kind !== "objective")
  if (lastPresent) return lastPresent.label
  return path?.scopeLabel?.trim() || null
}

export function formatRecordedAt(value: string | null, now: Date = new Date()): string {
  if (!value) return "—"
  const parsed = new Date(value.replace(" ", "T") + (/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? "" : "Z"))
  if (Number.isNaN(parsed.getTime())) return value
  const sameDay = parsed.toDateString() === now.toDateString()
  if (sameDay) return "Today"
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

const SIGN_IN_STATUSES = new Set(["pending", "pending_auth", "needs_connection", "auth_expired"])

export function connectorsNeedingSignIn(connectors: Connector[] | null | undefined): Connector[] {
  return (connectors ?? []).filter((c) => SIGN_IN_STATUSES.has(String(c.status ?? "").toLowerCase()))
}

export type ReportSources = {
  pageContext?: IntelligencePageContextResponse | null
  metricsReady: boolean
  roi?: AgentRoiReport | null
  roiLoading?: boolean
  roiError?: boolean
  connectors?: Connector[] | null
  connectorsLoading?: boolean
  connectorsError?: boolean
  auditTotal?: number | null
  auditLoading?: boolean
  auditError?: boolean
}

export function buildTemplateKpis(template: ReportTemplateId, src: ReportSources): ReportKpi[] {
  const ctx = src.pageContext
  const outcomes = ctx?.metrics.outcomes ?? ctx?.snapshot.metrics.outcomes ?? {}
  const execution = ctx?.metrics.execution ?? ctx?.snapshot.metrics.execution ?? {}
  const predictionMetrics = ctx?.metrics.predictions ?? ctx?.snapshot.metrics.predictions ?? {}

  if (template === "business") {
    const measured = src.metricsReady ? readNumber(outcomes.measuredOutcomes, null) : null
    const steps = toTrailSteps(pickTrailPath(ctx?.outcomePaths))
    const present = steps.filter((s) => s.present).length
    const revenue = src.roi?.orgTotals?.revenueInfluencedUsd
    return [
      src.metricsReady
        ? {
            label: "Measured outcomes",
            value: measured == null ? "—" : String(measured),
            note: measured == null ? "Not measured yet" : "Results backed by evidence",
            evidence: measured == null ? "none" : "measured",
          }
        : pending("Measured outcomes"),
      src.metricsReady
        ? steps.length
          ? {
              label: "Steps with evidence",
              value: `${present} of ${steps.length}`,
              note: "On the latest outcome",
              evidence: "measured",
            }
          : { label: "Steps with evidence", value: "—", note: "No evidence trail yet", evidence: "none" }
        : pending("Steps with evidence"),
      src.roiLoading && !src.roi
        ? pending("Revenue influenced")
        : src.roiError
          ? { label: "Revenue influenced", value: "—", note: "Could not load revenue data", evidence: "none" }
          : roiKpi("Revenue influenced", revenue, revenue?.note || "From recorded outcomes", "Turn on revenue tracking"),
    ]
  }

  if (template === "agent") {
    if (src.roiLoading && !src.roi) return [pending("Runs"), pending("Time saved"), pending("Cost")]
    if (src.roiError || !src.roi?.orgTotals) {
      const note = src.roiError ? "Could not load agent data" : "No agent data yet"
      return [
        { label: "Runs", value: "—", note, evidence: "none" },
        { label: "Time saved", value: "—", note, evidence: "none" },
        { label: "Cost", value: "—", note, evidence: "none" },
      ]
    }
    const totals = src.roi.orgTotals
    const actions = readNumber(totals.actionsExecuted?.value, null)
    const agentCount = src.roi.agents?.length ?? 0
    return [
      roiKpi(
        "Runs",
        totals.tasksCompleted,
        actions == null ? "Tasks completed this period" : `${plural(actions, "action")} executed`,
        "No runs recorded this period",
      ),
      roiKpi("Time saved", totals.estimatedHoursSaved, "From task type and duration", "Not enough runs to estimate"),
      roiKpi(
        "Cost",
        totals.agentCostUsd,
        agentCount ? `Across ${plural(agentCount, "agent")}` : "Model usage this period",
        "No usage recorded this period",
      ),
    ]
  }

  if (template === "prediction") {
    if (!src.metricsReady) return [pending("Active forecasts"), pending("Need you now"), pending("Track record")]
    const predictions = formatPredictions(ctx?.snapshot.predictions as Record<string, unknown>[] | undefined)
    const risks = predictions.filter((p) => p.kind === "risk").length
    const opportunities = predictions.filter((p) => p.kind === "opportunity").length
    const active = readNumber(predictionMetrics.activePredictions, null) ?? predictions.length
    const urgent = readNumber(predictionMetrics.highPriorityPredictions, null)
    const events = (ctx?.snapshot.outcomes ?? []) as Array<Record<string, unknown>>
    const validated = events.filter((e) => e.event === "prediction_validated").length
    const missed = events.filter((e) => e.event === "prediction_missed").length
    const scored = validated + missed
    return [
      {
        label: "Active forecasts",
        value: String(active),
        note: active ? `${plural(risks, "risk")} · ${plural(opportunities, "opportunity", "opportunities")}` : "No forecasts yet",
        evidence: "measured",
      },
      urgent == null
        ? { label: "Need you now", value: "—", note: "Not scored yet", evidence: "none" }
        : {
            label: "Need you now",
            value: String(urgent),
            note: urgent ? "Moderate confidence or higher" : "Nothing urgent",
            evidence: "measured",
          },
      scored
        ? {
            label: "Track record",
            value: `${Math.round((validated / scored) * 100)}%`,
            note: `${plural(scored, "forecast")} scored`,
            evidence: "measured",
          }
        : { label: "Track record", value: "—", note: "No outcomes marked yet", evidence: "none" },
    ]
  }

  // governance
  const awaiting = src.metricsReady ? readNumber(execution.awaitingApproval, null) : null
  const signIn = connectorsNeedingSignIn(src.connectors)
  return [
    src.metricsReady
      ? awaiting == null
        ? { label: "Waiting for approval", value: "—", note: "Not measured yet", evidence: "none" }
        : {
            label: "Waiting for approval",
            value: String(awaiting),
            note: awaiting ? "Pending governed actions" : "Nothing waiting on a person",
            evidence: "measured",
          }
      : pending("Waiting for approval"),
    src.connectorsLoading && !src.connectors
      ? pending("Connectors needing sign-in")
      : src.connectorsError
        ? { label: "Connectors needing sign-in", value: "—", note: "Could not load connectors", evidence: "none" }
        : {
            label: "Connectors needing sign-in",
            value: String(signIn.length),
            note: signIn.length
              ? signIn
                  .slice(0, 2)
                  .map((c) => c.name)
                  .join(", ") + (signIn.length > 2 ? ` and ${signIn.length - 2} more` : "")
              : "All connectors signed in",
            evidence: "measured",
          },
    src.auditLoading && src.auditTotal == null
      ? pending("Audit events")
      : src.auditError || src.auditTotal == null
        ? { label: "Audit events", value: "—", note: "Audit log not available", evidence: "none" }
        : {
            label: "Audit events",
            value: String(src.auditTotal),
            note: src.auditTotal ? "Changes recorded this period" : "Nothing changed this period",
            evidence: "measured",
          },
  ]
}
