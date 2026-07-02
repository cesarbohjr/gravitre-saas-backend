import { apiFetch } from "@/lib/fetcher"
import type { AgentJob, AgentJobResult } from "@/hooks/use-async-job"
import {
  buildFindingsFromJobResult,
  buildOperatorJobContext,
  type OperatorInsightSection,
} from "@/lib/operator-plan"

export type ActionPlanStep = {
  step: number
  title: string
  description: string
  status: "completed" | "current" | "pending"
}

export type InlineSuggestedAction = {
  id: string
  title: string
  description: string
  type: "immediate" | "scheduled" | "requires-approval"
  priority: "critical" | "high" | "medium" | "low"
  estimatedImpact?: string
  icon?: "zap" | "refresh" | "play" | "shield" | "clock"
}

export type InlineExecutePlan = {
  findings: OperatorInsightSection[]
  steps: ActionPlanStep[]
  suggestedActions: InlineSuggestedAction[]
}

export const DEFAULT_OPERATOR_CONTEXT = "connector-sf"

export const fallbackInsightSections: OperatorInsightSection[] = [
  {
    id: "summary",
    type: "summary",
    title: "What Happened",
    content:
      "The nightly Salesforce sync failed during the transformation step. The connector timed out after 30 seconds while waiting for a response from the Salesforce API.",
  },
  {
    id: "root-cause",
    type: "root-cause",
    title: "Why It Happened",
    content:
      "Peak-hour API latency pushed response times above the configured 30s timeout. The connector does not retry transient failures automatically.",
  },
  {
    id: "actions",
    type: "actions",
    title: "How to Fix It",
    content: "Recommended remediation steps based on similar incidents:",
    actions: [
      { id: "a1", label: "Increase timeout threshold to 60s", priority: "high" },
      { id: "a2", label: "Add retry logic with exponential backoff", priority: "medium" },
    ],
  },
  {
    id: "prevention",
    type: "prevention",
    title: "Prevention",
    content:
      "Schedule syncs before peak API hours, enable a circuit breaker on the Salesforce connector, and alert when response times exceed 15 seconds.",
  },
]

export const fallbackActionPlanSteps: ActionPlanStep[] = [
  {
    step: 1,
    title: "Analyze context",
    description: "Review task and gather information",
    status: "completed",
  },
  {
    step: 2,
    title: "Run workflow",
    description: "Execute recommended remediation",
    status: "current",
  },
  {
    step: 3,
    title: "Verify outcome",
    description: "Confirm sync succeeds on retry",
    status: "pending",
  },
]

export const fallbackSuggestedActionsList: InlineSuggestedAction[] = [
  {
    id: "action-1",
    title: "Increase timeout threshold to 60s",
    description: "Modify the transformation step timeout from 30s to 60s to handle peak hour latency",
    type: "immediate",
    priority: "critical",
    estimatedImpact: "Resolves 87% of timeout failures during peak hours",
    icon: "zap",
  },
  {
    id: "action-2",
    title: "Add retry logic with exponential backoff",
    description: "Implement automatic retries with 1s, 2s, 4s delays before failing",
    type: "requires-approval",
    priority: "high",
    estimatedImpact: "Reduces transient failures by 65%",
    icon: "refresh",
  },
  {
    id: "action-3",
    title: "Schedule sync before 2 PM UTC",
    description: "Move the daily sync window to avoid peak API traffic hours",
    type: "scheduled",
    priority: "medium",
    estimatedImpact: "Avoids 94% of rate limit issues",
    icon: "clock",
  },
  {
    id: "action-4",
    title: "Enable circuit breaker pattern",
    description: "Add circuit breaker to Salesforce connector to prevent cascade failures",
    type: "requires-approval",
    priority: "low",
    estimatedImpact: "Improves system resilience during outages",
    icon: "shield",
  },
]

function normalizeConfidenceScore(value: number | undefined | null): number | null {
  if (value == null || Number.isNaN(value)) return null
  if (value > 0 && value <= 1) return Math.round(value * 100)
  return Math.round(Math.min(100, Math.max(0, value)))
}

export function resolveAnalysisConfidence(
  plan: InlineExecutePlan | null,
  job: AgentJob | null,
): number {
  if (job?.status === "completed" && job.result?.confidence != null) {
    const fromJob = normalizeConfidenceScore(job.result.confidence)
    if (fromJob != null) return fromJob
  }
  const traceCount = Array.isArray(job?.result?.react_trace) ? job.result.react_trace.length : 0
  if (traceCount > 0) return Math.min(95, 70 + traceCount * 5)
  return 87
}

export function resolveConfidenceDataPoints(
  job: AgentJob | null,
  sections: OperatorInsightSection[],
): number {
  const trace = job?.result?.react_trace
  const traceCount = Array.isArray(trace) ? trace.filter(Boolean).length : 0
  const ragCount = Array.isArray(job?.result?.rag_sources) ? job.result.rag_sources.length : 0
  if (traceCount + ragCount > 0) return traceCount + ragCount
  return sections.length
}

export function planFromJobResult(job: AgentJob): InlineExecutePlan {
  const result = job.result as AgentJobResult
  const findings = buildFindingsFromJobResult(result)
  return {
    findings,
    steps: [
      {
        step: 1,
        title: "Analyze context",
        description: "Review task and gather information",
        status: "completed",
      },
      {
        step: 2,
        title: result.action_title || "Suggested Action",
        description: result.action_description || "Execute recommended action",
        status: "current",
      },
      {
        step: 3,
        title: "Verify outcome",
        description: "Confirm the fix resolves the incident",
        status: "pending",
      },
    ],
    suggestedActions: result.action_title
      ? [
          {
            id: `action-${job.jobId}`,
            title: result.action_title,
            description: result.action_description || "Apply the suggested fix",
            type: result.requires_approval ? "requires-approval" : "immediate",
            priority: "high",
            estimatedImpact: "Based on agent analysis",
            icon: "refresh",
          },
          ...fallbackSuggestedActionsList.slice(1),
        ]
      : fallbackSuggestedActionsList,
  }
}

export function planFromSyncResponse(data: {
  plan?: {
    reasoning?: OperatorInsightSection[]
    steps?: ActionPlanStep[]
    proposals?: InlineSuggestedAction[]
  }
}): InlineExecutePlan {
  return {
    findings: data.plan?.reasoning ?? fallbackInsightSections,
    steps: data.plan?.steps ?? fallbackActionPlanSteps,
    suggestedActions: data.plan?.proposals ?? fallbackSuggestedActionsList,
  }
}

export async function createOperatorSession(title: string): Promise<string | null> {
  const response = await apiFetch("/api/operators/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title.trim().slice(0, 120) || "Gravitre AI task" }),
  })
  if (!response.ok) return null
  const data = (await response.json()) as { session?: { id?: string }; id?: string }
  return data.session?.id ?? data.id ?? null
}

export async function runSyncOperatorTask(
  sessionId: string,
  task: string,
  activeContext = DEFAULT_OPERATOR_CONTEXT,
): Promise<InlineExecutePlan> {
  const response = await apiFetch(`/api/operators/sessions/${sessionId}/task`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task,
      context: buildOperatorJobContext(activeContext),
    }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const message =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail ?? "")
        : "The operator service returned an error."
    throw new Error(message || "Couldn't generate a plan")
  }
  const data = await response.json()
  return planFromSyncResponse(data)
}

export function buildOperatorJobPayload(
  sessionId: string | null,
  task: string,
  activeContext = DEFAULT_OPERATOR_CONTEXT,
) {
  return {
    sessionId: sessionId ?? undefined,
    context: buildOperatorJobContext(activeContext),
  }
}
