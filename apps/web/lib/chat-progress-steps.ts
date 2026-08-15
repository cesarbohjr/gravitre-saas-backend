/**
 * Shared derivation of NAMED progress steps for the Chat surfaces.
 *
 * Both the inline plan bar (`research-plan-panel.tsx`) and the task side panel
 * (`task-side-panel.tsx`) previously parsed the raw SSE `progressSteps` strings
 * themselves, which let their labels drift: the panel stripped the
 * "Running: " / "Completed: " prefixes while the inline bar printed them
 * verbatim. This module is the single source of truth so a step reads the same
 * in both places.
 *
 * Input shapes (unchanged, no new stores):
 *  - SSE `progressSteps`: "Running: …" | "Completed: …" | "Step N/M: …"
 *  - `pendingTask.params.steps[].label` + `current_step_index`
 */

export type ProgressStepStatus = "done" | "current" | "pending"

export type NamedProgressStep = {
  /** Human label with any status prefix stripped. Never "Routing tier: research". */
  label: string
  status: ProgressStepStatus
}

type PendingLike = {
  params?: {
    steps?: unknown[] | null
    current_step_index?: unknown
  } | null
} | null | undefined

/** Matches the status-prefixed strings the backend emits over SSE. */
export const ACTION_STEP_PATTERN = /^(Running:|Completed:|Step \d+\/\d+:)/i

/** Context-phase labels from `build_progress_steps(phase="context")` — agent bubble only. */
const CONTEXT_STEP_PATTERN =
  /^(classifying request|checking .+|loading memory and knowledge|preparing actions for .+|running .+ analysis)/i

export function isActionProgressStep(step: string): boolean {
  return ACTION_STEP_PATTERN.test(String(step).trim())
}

export function isContextProgressStep(step: string): boolean {
  const label = stripStepPrefix(String(step ?? "").trim())
  return Boolean(label && CONTEXT_STEP_PATTERN.test(label))
}

/**
 * Internal routing chatter that must never surface as a user-facing step label.
 * The brief calls this out explicitly ("never 'Routing tier: research'").
 */
const INTERNAL_LABEL_PATTERN = /^(routing tier|tier|engine|model|strategy)\s*:/i

function stripStepPrefix(text: string): string {
  return text
    .replace(/^Completed:\s*/i, "")
    .replace(/^Running:\s*/i, "")
    .replace(/^Step \d+\/\d+:\s*/i, "")
    .trim()
}

/**
 * Derives named steps, preferring live SSE progress and falling back to the
 * planned steps on `pendingTask`.
 */
export function deriveNamedProgressSteps(
  progressSteps: string[] | null | undefined,
  pendingTask: PendingLike,
): NamedProgressStep[] {
  const fromProgress: NamedProgressStep[] = []

  for (const raw of progressSteps ?? []) {
    const text = String(raw ?? "").trim()
    if (!text) continue

    const label = stripStepPrefix(text)
    // Drop internal routing lines, context-phase chatter, and empty labels.
    if (!label || INTERNAL_LABEL_PATTERN.test(label) || isContextProgressStep(text)) continue

    if (/^Completed:/i.test(text)) {
      fromProgress.push({ label, status: "done" })
    } else if (/^Running:/i.test(text)) {
      fromProgress.push({ label, status: "current" })
    } else {
      fromProgress.push({ label, status: "pending" })
    }
  }

  if (fromProgress.length > 0) return fromProgress

  const steps = pendingTask?.params?.steps
  if (!Array.isArray(steps)) return []

  const currentIdx = Number(pendingTask?.params?.current_step_index ?? -1)
  return steps
    .map((step, index) => {
      const rawLabel =
        step && typeof step === "object" && "label" in step
          ? String((step as { label?: unknown }).label ?? "")
          : ""
      const label = stripStepPrefix(rawLabel) || `Step ${index + 1}`
      const status: ProgressStepStatus =
        currentIdx >= 0 && index < currentIdx
          ? "done"
          : currentIdx >= 0 && index === currentIdx
            ? "current"
            : "pending"
      return { label, status }
    })
    .filter((step) => !INTERNAL_LABEL_PATTERN.test(step.label))
}

/**
 * "Step 2 of 5" while running, else "5 steps". Returns null when there is
 * nothing to count, so callers can omit the counter entirely.
 */
export function formatStepCounter(steps: NamedProgressStep[]): string | null {
  if (steps.length === 0) return null
  const currentIdx = steps.findIndex((step) => step.status === "current")
  if (currentIdx >= 0) return `Step ${currentIdx + 1} of ${steps.length}`
  const doneCount = steps.filter((step) => step.status === "done").length
  if (doneCount === steps.length) return `${steps.length} of ${steps.length} complete`
  return `${steps.length} step${steps.length === 1 ? "" : "s"}`
}
