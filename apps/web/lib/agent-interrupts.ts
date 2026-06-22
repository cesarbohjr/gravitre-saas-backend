/**
 * STA-108 / STA-170: unified human-in-the-loop interrupt channel.
 * All UI pause/cancel actions should route through POST /api/agent-interrupts.
 */
import { apiFetch } from "@/lib/fetcher"
import type { AgentInterrupt, AgentInterruptSignal, AgentInterruptTargetType } from "@/types/api"

function extractErrorMessage(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined
  const record = error as Record<string, unknown>
  if (typeof record.detail === "string") return record.detail
  if (typeof record.error === "string") return record.error
  if (typeof record.message === "string") return record.message
  return undefined
}

export async function requestAgentInterrupt(
  targetType: AgentInterruptTargetType,
  targetId: string,
  signal: AgentInterruptSignal,
): Promise<AgentInterrupt> {
  const response = await apiFetch("/api/agent-interrupts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targetType, targetId, signal }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractErrorMessage(error) || `Interrupt request failed: ${response.status}`)
  }
  const payload = (await response.json()) as { interrupt?: AgentInterrupt }
  if (!payload.interrupt) {
    throw new Error("Interrupt response missing interrupt payload")
  }
  return payload.interrupt
}

export function interruptRequestedMessage(signal: AgentInterruptSignal): string {
  if (signal === "pause") {
    return "Pause interrupt queued — execution stops before the next step."
  }
  return "Cancel interrupt queued — execution stops before the next step."
}

export function interruptRequestedDescription(): string {
  return "Sent via the agent interrupt channel (UI, Slack, or API)."
}
