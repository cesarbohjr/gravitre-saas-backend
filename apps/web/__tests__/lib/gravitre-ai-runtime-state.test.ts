import { describe, expect, it } from "vitest"
import {
  AI_RUNTIME_STATES,
  AI_RUNTIME_STATES_WITH_PRODUCTION_SIGNAL,
  deriveAiRuntimeState,
  isApprovalPanelVisible,
  isQueuedForApprover,
  type AiRuntimeStateInput,
} from "@/lib/gravitre-ai-runtime-state"

const base: AiRuntimeStateInput = { status: "ready" }

describe("deriveAiRuntimeState — every state comes from a real bridge prop", () => {
  it("idle when nothing is happening", () => {
    expect(deriveAiRuntimeState(base)).toBe("idle")
  })

  it("streaming from useChat status or isStreaming", () => {
    expect(deriveAiRuntimeState({ ...base, status: "streaming" })).toBe("streaming")
    expect(deriveAiRuntimeState({ ...base, isStreaming: true })).toBe("streaming")
  })

  it("generating while submitted/busy or executing an approved action", () => {
    expect(deriveAiRuntimeState({ ...base, status: "submitted" })).toBe("generating")
    expect(deriveAiRuntimeState({ ...base, isBusy: true })).toBe("generating")
    expect(deriveAiRuntimeState({ ...base, confirmExecuting: true })).toBe("generating")
  })

  it("needs_approval only when the execution panel would show an Approve button", () => {
    const input: AiRuntimeStateInput = {
      ...base,
      dialogueMode: "confirm",
      canApprove: true,
      pendingTask: { type: "connector_action", status: "awaiting_confirm" },
    }
    expect(isApprovalPanelVisible(input)).toBe(true)
    expect(isQueuedForApprover(input)).toBe(false)
    expect(deriveAiRuntimeState(input)).toBe("needs_approval")
  })

  it("blocked when the request is queued for another approver", () => {
    expect(
      deriveAiRuntimeState({
        ...base,
        dialogueMode: "awaiting_approval",
        pendingTask: { type: "connector_action" },
      }),
    ).toBe("blocked")
    expect(
      deriveAiRuntimeState({
        ...base,
        dialogueMode: "confirm",
        canApprove: false,
        pendingTask: { type: "connector_action", status: "awaiting_plan_confirm" },
      }),
    ).toBe("blocked")
  })

  it("does not claim approval when the panel would not render one", () => {
    expect(deriveAiRuntimeState({ ...base, dialogueMode: "execute", pendingTask: { type: "connector_action" } })).toBe("idle")
    expect(deriveAiRuntimeState({ ...base, dialogueMode: "confirm", pendingTask: {} })).toBe("idle")
  })

  it("failed from an error turn or an unsuccessful execution result", () => {
    expect(deriveAiRuntimeState({ ...base, status: "error" })).toBe("failed")
    expect(deriveAiRuntimeState({ ...base, executionResult: { success: false } })).toBe("failed")
  })

  it("partial from a stopped turn or a completed run with failed steps", () => {
    expect(deriveAiRuntimeState({ ...base, canContinueAfterStop: true })).toBe("partial")
    expect(
      deriveAiRuntimeState({
        ...base,
        executionResult: { success: true, structured: { stepBreakdown: [{ success: true }, { success: false }] } },
      }),
    ).toBe("partial")
  })

  it("completed from a successful execution result", () => {
    expect(deriveAiRuntimeState({ ...base, executionResult: { success: true } })).toBe("completed")
  })

  it("an in-flight turn outranks a stale completed result", () => {
    expect(deriveAiRuntimeState({ ...base, status: "streaming", executionResult: { success: true } })).toBe("streaming")
  })

  it("never derives `resumed` — there is no production signal for it", () => {
    expect(AI_RUNTIME_STATES).toContain("resumed")
    expect(AI_RUNTIME_STATES_WITH_PRODUCTION_SIGNAL).not.toContain("resumed")
    const statuses = ["ready", "submitted", "streaming", "error"] as const
    for (const status of statuses) {
      for (const flag of [true, false]) {
        expect(
          deriveAiRuntimeState({
            status,
            isBusy: flag,
            isStreaming: flag,
            confirmExecuting: flag,
            canContinueAfterStop: flag,
            executionResult: flag ? { success: true } : null,
          }),
        ).not.toBe("resumed")
      }
    }
  })
})
