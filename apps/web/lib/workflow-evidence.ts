/** Evidence from a simulation response; never substitute local timing profiles. */
export function reportedCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null
}

export function simulationDuration(step: Record<string, unknown>): number | null {
  const start = step.started_at ?? step.startedAt
  const end = step.completed_at ?? step.completedAt
  if (typeof start !== "string" || typeof end !== "string") return null
  const duration = Date.parse(end) - Date.parse(start)
  return reportedCount(duration)
}

export function totalSimulationDuration(
  steps: Array<{ predictedMs: number | null }> | null,
): number | null {
  if (!steps?.length || steps.some((step) => step.predictedMs === null)) return null
  return steps.reduce((sum, step) => sum + (step.predictedMs ?? 0), 0)
}

export function formatSimulationDuration(ms: number | null): string {
  if (ms === null) return "Not reported"
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function isSuccessfulWorkflowStatus(status: string | null | undefined): boolean {
  return ["completed", "success", "succeeded"].includes(status?.toLowerCase() ?? "")
}
