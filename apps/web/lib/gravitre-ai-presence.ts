/**
 * Pure presence-state derivation for the Gravitre AI Helper bubble and the
 * GravitreFloatingWorkspace window header — Phase 2 of the "Gravitre AI
 * Agent Workspace" redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Finding A6: the existing `VoicePresenceState` union has no `executing` or
 * `needs_approval` state — those are chat-level concepts. This is the "new,
 * superset state model" the architecture doc calls for, built directly from
 * the real snapshot fields `GravitreAIWorkspaceProvider` already publishes
 * (Phase 1) — never from mock/fake data.
 *
 * Deliberately a pure function, independent of React, so it is testable
 * without jsdom/react-dom.
 */
import type {
  GravitreAIApprovalSnapshot,
  GravitreAIConversationSnapshot,
  GravitreAIVoiceSnapshot,
} from "@/components/gravitre/ai-workspace-provider"

/**
 * Superset of the Phase 0 prototype's `PresenceState` mock union, minus
 * "working" (folded into "thinking" — there is no real signal today that
 * distinguishes the two; inventing one would be exactly the kind of fake
 * state this file exists to avoid).
 */
export type GravitreHelperPresence =
  | "ready"
  | "listening"
  | "thinking"
  | "executing"
  | "needs_approval"
  | "complete"
  | "error"

export interface GravitreHelperPresenceInput {
  conversation: GravitreAIConversationSnapshot | null
  approval: GravitreAIApprovalSnapshot | null
  voice: GravitreAIVoiceSnapshot | null
}

/**
 * Derives a single presence state from the real conversation/approval/voice
 * snapshots published by `GravitreAIConversationTranscript` /
 * `GravitreAIConversationComposer` (Phase 1) into the shared provider.
 *
 * Precedence (highest first): error > needing your approval right now >
 * actively executing an approved action > actively listening for voice input
 * > actively streaming/thinking > recently completed an execution > ready.
 */
export function deriveGravitreHelperPresence({
  conversation,
  approval,
  voice,
}: GravitreHelperPresenceInput): GravitreHelperPresence {
  if (conversation?.status === "error") return "error"

  if (approval?.confirmExecuting) return "executing"

  if (approval?.pendingTask) return "needs_approval"

  if (voice?.presence === "listening" || voice?.presence === "understanding") {
    return "listening"
  }

  if (
    conversation?.isStreaming ||
    conversation?.status === "streaming" ||
    conversation?.status === "submitted" ||
    conversation?.isBusy
  ) {
    return "thinking"
  }

  if (approval?.executionResult) return "complete"

  return "ready"
}

export const GRAVITRE_HELPER_PRESENCE_COPY: Record<GravitreHelperPresence, { label: string; tone: string }> = {
  ready: { label: "Ready", tone: "text-[color:var(--g-text-muted)]" },
  listening: { label: "Listening", tone: "text-[color:var(--g-signal)]" },
  thinking: { label: "Thinking", tone: "text-[color:var(--g-intelligence)]" },
  executing: { label: "Executing", tone: "text-[color:var(--g-signal)]" },
  needs_approval: { label: "Needs approval", tone: "text-[color:var(--g-approval)]" },
  complete: { label: "Complete", tone: "text-[color:var(--g-brand)]" },
  error: { label: "Error", tone: "text-[color:var(--g-danger)]" },
}

export const GRAVITRE_HELPER_PRESENCE_DOT: Record<GravitreHelperPresence, string> = {
  ready: "bg-[color:var(--g-text-muted)]",
  listening: "bg-[color:var(--g-signal)]",
  thinking: "bg-[color:var(--g-intelligence)]",
  executing: "bg-[color:var(--g-signal)]",
  needs_approval: "bg-[color:var(--g-approval)]",
  complete: "bg-[color:var(--g-brand)]",
  error: "bg-[color:var(--g-danger)]",
}
