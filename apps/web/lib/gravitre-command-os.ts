/**
 * UX Reset 2.0 Command OS helpers — inspector + work visibility.
 * Shared interaction: no selection → no inspector.
 */
import { shouldShowTaskSidePanel } from "@/lib/task-side-panel-threshold"

export type CommandOsPendingLike = {
  params?: {
    steps?: unknown[] | null
  } | null
} | null | undefined

export type CommandOsExecutionLike = {
  success?: boolean
  body?: string | null
  title?: string | null
  task_label?: string | null
  result_url?: string | null
  artifacts?: unknown[] | null
  structured?: unknown | null
} | null | undefined

export function shouldRevealInspector(input: {
  progressSteps?: string[] | null
  pendingTask?: CommandOsPendingLike
  inspectSelection?: unknown | null
}): boolean {
  if (input.inspectSelection != null && input.inspectSelection !== false) return true
  return shouldShowTaskSidePanel(input.progressSteps, input.pendingTask)
}

export function hasWorkArtifact(input: {
  executionResult?: CommandOsExecutionLike
  pendingTask?: unknown | null
  hostedFiles?: unknown[] | null
}): boolean {
  if ((input.hostedFiles?.length ?? 0) > 0) return true
  if (input.pendingTask) return true
  const result = input.executionResult
  if (!result) return false
  if (Array.isArray(result.artifacts) && result.artifacts.length > 0) return true
  if (result.structured) return true
  return Boolean(
    result.body ||
      result.title ||
      result.task_label ||
      result.result_url ||
      result.success === true ||
      result.success === false,
  )
}
