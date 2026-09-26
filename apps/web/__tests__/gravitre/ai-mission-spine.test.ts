import { describe, expect, it } from "vitest"
import type { UIMessage } from "ai"
import { deriveMissionStages } from "@/app/ai/_components/ai-mission-spine"

const user = (text: string): UIMessage => ({ id: "u1", role: "user", parts: [{ type: "text", text }] }) as UIMessage
const assistant = (text: string): UIMessage =>
  ({ id: "a1", role: "assistant", parts: [{ type: "text", text }] }) as UIMessage

function states(stages: ReturnType<typeof deriveMissionStages>) {
  return Object.fromEntries(stages.map((stage) => [stage.id, stage.state]))
}

describe("AI mission stages", () => {
  it("waits on the objective before any message", () => {
    const stages = deriveMissionStages({ messages: [], runtimeState: "idle" })
    expect(stages.map((stage) => stage.id)).toEqual(["objective", "plan", "work", "artifact", "approval", "result"])
    expect(states(stages)).toEqual({
      objective: "current",
      plan: "pending",
      work: "pending",
      artifact: "pending",
      approval: "not_needed",
      result: "pending",
    })
  })

  it("shows work in progress while streaming without claiming a plan or result", () => {
    const stages = deriveMissionStages({ messages: [user("Summarize renewals")], runtimeState: "streaming" })
    expect(stages[0].detail).toBe("Summarize renewals")
    expect(states(stages)).toMatchObject({ objective: "done", plan: "pending", work: "current", result: "pending" })
  })

  it("flags approval and failure only from runtime signals", () => {
    const waiting = deriveMissionStages({
      messages: [user("Send the email"), assistant("Ready")],
      runtimeState: "needs_approval",
      progressSteps: ["Draft", "Send"],
    })
    expect(states(waiting)).toMatchObject({ plan: "done", approval: "attention", work: "done" })

    const failed = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "failed" })
    expect(states(failed).result).toBe("failed")
  })

  it("marks the result answered once a completed reply exists", () => {
    const done = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "completed" })
    expect(done.find((stage) => stage.id === "result")).toMatchObject({ state: "done", detail: "Answered" })
    const settled = deriveMissionStages({ messages: [user("x"), assistant("y")], runtimeState: "idle" })
    expect(states(settled).result).toBe("done")
  })
})
