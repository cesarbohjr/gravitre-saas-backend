/**
 * UX Reset 2.0 Runs — outcome/evidence copy from recorded run fields only.
 * Never invent a business result, system, or duration bar.
 */

export type RunOutcomeStepLike = {
  name?: string
  status?: string
  errorMessage?: string | null
  outputSnapshot?: Record<string, unknown> | null
}

function trimText(value: unknown): string | null {
  if (typeof value !== "string") return null
  const next = value.trim()
  return next.length > 0 ? next : null
}

export function runOutcomeHeadline(input: {
  businessTitle?: string | null
  goal?: string | null
  lastCompletedSummary?: string | null
}): string | null {
  return (
    trimText(input.businessTitle) ||
    trimText(input.goal) ||
    trimText(input.lastCompletedSummary) ||
    null
  )
}

export function stepOutputSummary(step: RunOutcomeStepLike | null | undefined): string | null {
  if (!step) return null
  const snap = step.outputSnapshot ?? {}
  return (
    trimText(snap.summary) ||
    trimText(snap.message) ||
    trimText(step.errorMessage) ||
    null
  )
}

export function lastCompletedStepSummary(steps: RunOutcomeStepLike[]): string | null {
  const completed = [...steps]
    .reverse()
    .find((step) => {
      const status = String(step.status ?? "").toLowerCase()
      return status === "completed" || status === "success"
    })
  return stepOutputSummary(completed)
}

export function collectRunSystems(steps: RunOutcomeStepLike[]): string[] {
  const systems = new Set<string>()
  for (const step of steps) {
    const snap = step.outputSnapshot ?? {}
    for (const key of ["vendor", "connector", "system", "systemName"]) {
      const value = trimText(snap[key])
      if (value) systems.add(value)
    }
    const action =
      trimText(snap.invoke_action) || trimText(snap.action) || trimText(snap.tool)
    if (action && action.includes(".")) {
      const vendor = action.split(".")[0]
      if (vendor) systems.add(vendor)
    }
  }
  return [...systems]
}

export function collectRunActions(steps: RunOutcomeStepLike[]): string[] {
  const actions: string[] = []
  for (const step of steps) {
    const snap = step.outputSnapshot ?? {}
    const action =
      trimText(snap.invoke_action) ||
      trimText(snap.action) ||
      trimText(step.name)
    if (action && !actions.includes(action)) actions.push(action)
  }
  return actions
}
