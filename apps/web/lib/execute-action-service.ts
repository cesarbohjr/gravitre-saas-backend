import { apiFetch } from "@/lib/fetcher"
import type { AgentJob } from "@/hooks/use-async-job"
import type { InlineSuggestedAction } from "@/lib/ai-inline-execute"

export type ExecuteActionKind = "immediate" | "scheduled" | "requires-approval" | "auto_fix"

export type ExecuteActionResult = {
  success: boolean
  message: string
  entityType?: string
  entityId?: string
  url?: string
}

export async function executeSuggestedAction(params: {
  action: InlineSuggestedAction
  job: AgentJob | null
  sourcePrompt?: string
}): Promise<ExecuteActionResult> {
  const response = await apiFetch("/api/operators/execute-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_id: params.action.id,
      action_type: params.action.type,
      title: params.action.title,
      description: params.action.description,
      priority: params.action.priority,
      source_job_id: params.job?.jobId,
      source_prompt: params.sourcePrompt,
      job_result: params.job?.result ?? null,
    }),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail ?? "")
        : "Action could not be executed."
    throw new Error(detail || "Action could not be executed.")
  }
  return payload as ExecuteActionResult
}

export async function executePlanApproval(params: {
  job: AgentJob | null
  sourcePrompt?: string
}): Promise<ExecuteActionResult> {
  const title = params.job?.result?.action_title || "Execute remediation plan"
  const description = params.job?.result?.action_description || params.sourcePrompt || title
  return executeSuggestedAction({
    action: {
      id: `plan-${params.job?.jobId ?? "current"}`,
      title: String(title),
      description: String(description),
      type: params.job?.result?.requires_approval ? "requires-approval" : "immediate",
      priority: "high",
    },
    job: params.job,
    sourcePrompt: params.sourcePrompt,
  })
}

export async function runAutoFix(params: {
  job: AgentJob | null
  sourcePrompt?: string
}): Promise<ExecuteActionResult> {
  const response = await apiFetch("/api/operators/execute-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_id: "auto-fix",
      action_type: "auto_fix",
      title: "Auto-fix from analysis",
      description: params.job?.result?.finding_description || params.sourcePrompt || "Apply recommended fix",
      source_job_id: params.job?.jobId,
      source_prompt: params.sourcePrompt,
      job_result: params.job?.result ?? null,
    }),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail)
        : "Auto-fix could not be started.",
    )
  }
  return payload as ExecuteActionResult
}
