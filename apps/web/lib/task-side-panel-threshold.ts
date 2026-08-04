/** Evidence-based threshold from Phase 0 (96% of recorded chat tasks are 1–2 steps). */
export const SIDE_PANEL_STEP_THRESHOLD = 3

type PendingLike = {
  params?: {
    steps?: unknown[] | null
  } | null
} | null | undefined

export function countPlannedOrExecutedSteps(
  progressSteps: string[] | null | undefined,
  pendingTask: PendingLike,
): number {
  const pendingCount = Array.isArray(pendingTask?.params?.steps)
    ? pendingTask!.params!.steps!.length
    : 0
  const fromProgress = (progressSteps ?? []).filter((step) =>
    /^(Running:|Completed:|Step \d+\/\d+:)/i.test(String(step).trim()),
  ).length
  return Math.max(pendingCount, fromProgress)
}

export function shouldShowTaskSidePanel(
  progressSteps: string[] | null | undefined,
  pendingTask: PendingLike,
): boolean {
  return countPlannedOrExecutedSteps(progressSteps, pendingTask) >= SIDE_PANEL_STEP_THRESHOLD
}
