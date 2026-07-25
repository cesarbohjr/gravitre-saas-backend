/**
 * Poll workflow runs and map backend step status onto builder canvas nodes (STA-166).
 */
import { runsApi } from "@/lib/api"
import type { RunDetailResponse } from "@/types/api"
import type { CanvasWorkflowNode, NodeState } from "@/lib/workflows/builder-persistence"

export interface RunMonitorStep {
  nodeId?: string | null
  stepId?: string | null
  name?: string
  status: string
  errorMessage?: string | null
}

export interface RunMonitorSnapshot {
  runId: string
  status: string
  steps: RunMonitorStep[]
  errorMessage?: string | null
}

const TERMINAL_RUN_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
  "canceled",
  "rejected",
  "error",
  "paused",
  "awaiting_approval",
  "pending_approval",
])

export function mapStepStatusToNodeState(status: string): NodeState {
  const normalized = status.toLowerCase()
  if (normalized === "running") return "running"
  if (normalized === "failed" || normalized === "error") return "error"
  if (normalized === "completed" || normalized === "success" || normalized === "skipped") {
    return "success"
  }
  if (normalized === "waiting" || normalized === "pending" || normalized === "waiting_approval") {
    return "waiting"
  }
  if (normalized === "evaluating") return "evaluating"
  return "idle"
}

export function applyRunStepsToNodes(
  nodes: CanvasWorkflowNode[],
  steps: RunMonitorStep[]
): CanvasWorkflowNode[] {
  const byNodeId = new Map<string, RunMonitorStep>()
  for (const step of steps) {
    const key = step.nodeId || step.stepId
    if (key) byNodeId.set(String(key), step)
  }

  return nodes.map((node) => {
    const step =
      byNodeId.get(node.id) ??
      steps.find((candidate) => candidate.name && candidate.name === node.name)
    if (!step) {
      return { ...node, state: "idle" as NodeState, stepError: undefined }
    }
    const state = mapStepStatusToNodeState(step.status)
    const failed = state === "error"
    return {
      ...node,
      state,
      stepError: failed && step.errorMessage ? step.errorMessage : undefined,
    }
  })
}

export function findFirstFailedStep(steps: RunMonitorStep[]): RunMonitorStep | null {
  return (
    steps.find((step) => {
      const status = step.status.toLowerCase()
      return status === "failed" || status === "error"
    }) ?? null
  )
}

export function formatFailedStepMessage(
  snapshot: RunMonitorSnapshot,
  nodes: CanvasWorkflowNode[],
): string {
  const failedStep = findFirstFailedStep(snapshot.steps)
  if (!failedStep) {
    return (
      snapshot.errorMessage ??
      "Workflow run failed. Open the run report for step-level details."
    )
  }
  const nodeName =
    nodes.find(
      (node) =>
        node.id === failedStep.nodeId ||
        node.id === failedStep.stepId ||
        (failedStep.name && node.name === failedStep.name),
    )?.name ??
    failedStep.name ??
    failedStep.nodeId ??
    "Unknown step"
  const detail = failedStep.errorMessage ?? snapshot.errorMessage ?? "Step failed"
  return `${nodeName}: ${detail}`
}

export function resolveFailedStepNodeId(
  snapshot: RunMonitorSnapshot,
  nodes: CanvasWorkflowNode[],
): string | null {
  const failedStep = findFirstFailedStep(snapshot.steps)
  if (!failedStep) return null
  const match = nodes.find(
    (node) =>
      node.id === failedStep.nodeId ||
      node.id === failedStep.stepId ||
      (failedStep.name && node.name === failedStep.name),
  )
  return match?.id ?? (failedStep.nodeId ? String(failedStep.nodeId) : null)
}

export function countActiveRunSteps(steps: RunMonitorStep[]): number {
  return steps.filter((step) => {
    const status = step.status.toLowerCase()
    return status === "completed" || status === "success" || status === "failed" || status === "error"
  }).length
}

export function isTerminalRunStatus(status: string): boolean {
  return TERMINAL_RUN_STATUSES.has(status.toLowerCase())
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function normalizeMonitorStep(raw: Record<string, unknown>): RunMonitorStep {
  return {
    nodeId: (raw.nodeId as string | null | undefined) ?? (raw.node_id as string | null | undefined) ?? null,
    stepId: (raw.stepId as string | null | undefined) ?? (raw.step_id as string | null | undefined) ?? null,
    name: (raw.name as string | undefined) ?? (raw.step_name as string | undefined),
    status: String(raw.status ?? "pending"),
    errorMessage:
      (raw.errorMessage as string | null | undefined) ??
      (raw.error_message as string | null | undefined) ??
      (raw.error as string | null | undefined) ??
      null,
  }
}

export function normalizeRunSnapshot(
  runId: string,
  payload: RunDetailResponse
): RunMonitorSnapshot {
  const run = payload.run
  return {
    runId,
    status: String(run.status ?? "running"),
    errorMessage: run.errorMessage ?? run.error ?? null,
    steps: (payload.steps ?? []).map((step) =>
      normalizeMonitorStep(step as unknown as Record<string, unknown>),
    ),
  }
}

export function mapExecuteSteps(
  steps: Array<Record<string, unknown>>
): RunMonitorStep[] {
  return steps.map(normalizeMonitorStep)
}

export async function pollWorkflowRun(
  runId: string,
  onUpdate: (snapshot: RunMonitorSnapshot) => void,
  options?: { intervalMs?: number; timeoutMs?: number }
): Promise<RunMonitorSnapshot> {
  const intervalMs = options?.intervalMs ?? 1500
  const timeoutMs = options?.timeoutMs ?? 120000
  const startedAt = Date.now()

  while (true) {
    const payload = await runsApi.getWithSteps(runId)
    const snapshot = normalizeRunSnapshot(runId, payload)
    onUpdate(snapshot)

    if (isTerminalRunStatus(snapshot.status)) {
      return snapshot
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error("Workflow run polling timed out")
    }
    await sleep(intervalMs)
  }
}
