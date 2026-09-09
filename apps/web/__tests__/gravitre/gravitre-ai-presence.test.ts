/**
 * deriveGravitreHelperPresence — pure function, Phase 2 of the "Gravitre AI
 * Agent Workspace" redesign. See lib/gravitre-ai-presence.ts.
 */
import { describe, expect, it } from "vitest"
import { deriveGravitreHelperPresence } from "@/lib/gravitre-ai-presence"
import type {
  GravitreAIApprovalSnapshot,
  GravitreAIConversationSnapshot,
  GravitreAIVoiceSnapshot,
} from "@/components/gravitre/ai-workspace-provider"

const baseConversation: GravitreAIConversationSnapshot = {
  routeKey: "/ai",
  activeConversationId: "conv-1",
  conversationTitle: "Chat",
  messages: [],
  status: "ready",
  isStreaming: false,
  isBusy: false,
}

const baseApproval: GravitreAIApprovalSnapshot = {
  dialogueMode: null,
  pendingTask: null,
  executionResult: null,
  confirmExecuting: false,
}

const baseVoice: GravitreAIVoiceSnapshot = {
  modality: "text",
  presence: "idle",
  billing: false,
}

describe("deriveGravitreHelperPresence", () => {
  it("defaults to 'ready' when there is no activity at all (null snapshots)", () => {
    expect(deriveGravitreHelperPresence({ conversation: null, approval: null, voice: null })).toBe("ready")
  })

  it("defaults to 'ready' with idle real snapshots", () => {
    expect(
      deriveGravitreHelperPresence({ conversation: baseConversation, approval: baseApproval, voice: baseVoice }),
    ).toBe("ready")
  })

  it("returns 'error' when the real conversation status is 'error'", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: { ...baseConversation, status: "error" },
        approval: baseApproval,
        voice: baseVoice,
      }),
    ).toBe("error")
  })

  it("returns 'needs_approval' when a real pendingTask is present", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: baseConversation,
        approval: { ...baseApproval, pendingTask: { title: "Send email" } as never },
        voice: baseVoice,
      }),
    ).toBe("needs_approval")
  })

  it("returns 'executing' when confirmExecuting is true, even with a pendingTask", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: baseConversation,
        approval: {
          ...baseApproval,
          pendingTask: { title: "Send email" } as never,
          confirmExecuting: true,
        },
        voice: baseVoice,
      }),
    ).toBe("executing")
  })

  it("returns 'listening' when the real voice snapshot is listening", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: baseConversation,
        approval: baseApproval,
        voice: { ...baseVoice, presence: "listening" },
      }),
    ).toBe("listening")
  })

  it("returns 'thinking' when the real conversation is streaming", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: { ...baseConversation, isStreaming: true, status: "streaming" },
        approval: baseApproval,
        voice: baseVoice,
      }),
    ).toBe("thinking")
  })

  it("returns 'thinking' when the real conversation is merely busy (not yet streaming)", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: { ...baseConversation, isBusy: true },
        approval: baseApproval,
        voice: baseVoice,
      }),
    ).toBe("thinking")
  })

  it("returns 'complete' when a real executionResult exists and nothing else is active", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: baseConversation,
        approval: { ...baseApproval, executionResult: { success: true } as never },
        voice: baseVoice,
      }),
    ).toBe("complete")
  })

  it("prioritizes 'error' over a stale executionResult", () => {
    expect(
      deriveGravitreHelperPresence({
        conversation: { ...baseConversation, status: "error" },
        approval: { ...baseApproval, executionResult: { success: true } as never },
        voice: baseVoice,
      }),
    ).toBe("error")
  })
})
