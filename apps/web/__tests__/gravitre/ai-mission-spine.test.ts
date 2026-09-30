import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { deriveMissionStages } from "@/app/ai/_components/ai-mission-spine"
import type { ChatExecutionResult } from "@/components/gravitre/assistant/chat-execution-panel"

const user = (text: string, id = "u1"): UIMessage => ({ id, role: "user", parts: [{ type: "text", text }] }) as UIMessage
const assistant = (text: string, id = "a1"): UIMessage =>
  ({ id, role: "assistant", parts: [{ type: "text", text }] }) as UIMessage

function states(stages: ReturnType<typeof deriveMissionStages>) {
  return Object.fromEntries(stages.map((stage) => [stage.id, stage.state]))
}

describe("AI mission stages", () => {
  it("shows every stage as not started before any message", () => {
    const stages = deriveMissionStages({ messages: [], runtimeState: "idle" })
    expect(stages.map((stage) => stage.id)).toEqual(["objective", "plan", "work", "artifact", "approval", "result"])
    expect(states(stages)).toEqual({
      objective: "pending",
      plan: "pending",
      work: "pending",
      artifact: "pending",
      approval: "not_needed",
      result: "pending",
    })
  })

  it("is waiting after submit, before the first response", () => {
    const stages = deriveMissionStages({ messages: [user("Summarize renewals")], runtimeState: "generating" })
    expect(stages[0]).toMatchObject({ state: "complete", detail: "Summarize renewals" })
    expect(states(stages)).toMatchObject({ plan: "pending", work: "waiting", result: "waiting" })
  })

  it("is active while the reply streams", () => {
    const stages = deriveMissionStages({ messages: [user("x"), assistant("partial")], runtimeState: "streaming" })
    expect(states(stages)).toMatchObject({ work: "active", result: "waiting" })
  })

  it("requires approval, or is blocked when queued for an approver", () => {
    const waiting = deriveMissionStages({
      messages: [user("Send the email"), assistant("Ready")],
      runtimeState: "needs_approval",
      progressSteps: ["Draft", "Send"],
    })
    expect(states(waiting)).toMatchObject({ plan: "complete", work: "complete", approval: "approval", result: "waiting" })

    const queued = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "blocked" })
    expect(states(queued)).toMatchObject({ approval: "blocked", result: "waiting" })
  })

  it("marks the result available only when an answer or delivery exists", () => {
    const answered = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "idle" })
    expect(answered.find((stage) => stage.id === "result")).toMatchObject({ state: "available", detail: "Answer ready" })

    const delivered = deriveMissionStages({
      messages: [user("x"), assistant("y")],
      runtimeState: "completed",
      executionResult: { success: true, title: "12 reminders sent", artifacts: [{}] } as unknown as ChatExecutionResult,
    })
    expect(states(delivered)).toMatchObject({ artifact: "available", approval: "not_needed", result: "available" })
    expect(delivered.find((stage) => stage.id === "result")?.detail).toBe("12 reminders sent")
  })


  it("only marks approval resolved when approval was actually required and terminal", () => {
    const terminal = deriveMissionStages({
      messages: [user("Send it"), assistant("Sent")],
      runtimeState: "failed",
      pendingTask: {
        type: "connector_action",
        status: "failed",
        params: { requires_approval: true },
      },
      executionResult: { success: false, body: "Provider rejected the send." },
    })
    expect(terminal.find((stage) => stage.id === "approval")).toMatchObject({
      state: "complete",
      detail: "Resolved",
    })

    const noApprovalEvidence = deriveMissionStages({
      messages: [user("Read my inbox"), assistant("Could not load it")],
      runtimeState: "failed",
      executionResult: { success: false, body: "Read failed." },
    })
    expect(noApprovalEvidence.find((stage) => stage.id === "approval")).toMatchObject({
      state: "not_needed",
      detail: "Not requested",
    })
  })

  it("reports failure and partial runs without claiming a result", () => {
    const failed = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "failed" })
    expect(states(failed)).toMatchObject({ work: "failed", result: "failed" })

    const partial = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "partial" })
    expect(states(partial)).toMatchObject({ work: "blocked", result: "blocked" })
  })

  it("tracks the latest turn, not an earlier reply", () => {
    const stages = deriveMissionStages({
      messages: [user("first"), assistant("done"), user("second", "u2")],
      runtimeState: "generating",
    })
    expect(stages[0].detail).toBe("second")
    expect(states(stages).work).toBe("waiting")
  })
})
