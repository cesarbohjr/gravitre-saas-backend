// @vitest-environment jsdom
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import type { UIMessage } from "ai"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  GravitreAIRuntimeDetails,
  runtimeInspectorFields,
  runtimeInspectorKind,
} from "@/components/gravitre/ai-runtime-details"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const messages: UIMessage[] = [
  { id: "u-1", role: "user", parts: [{ type: "text", text: "hi" }] },
  { id: "a-1", role: "assistant", parts: [{ type: "text", text: "hello" }] },
]

let container: HTMLDivElement
let root: Root | null = null
beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
})
afterEach(() => {
  if (root) act(() => root!.unmount())
  root = null
  container.remove()
})

describe("runtime inspector", () => {
  it("maps states to inspector kinds", () => {
    expect(runtimeInspectorKind("failed")).toBe("error")
    expect(runtimeInspectorKind("needs_approval")).toBe("approval")
    expect(runtimeInspectorKind("blocked")).toBe("approval")
    expect(runtimeInspectorKind("partial")).toBe("task")
    expect(runtimeInspectorKind("completed")).toBe("task")
  })

  it("shows only what the runtime reported", () => {
    const { turn, result, task } = runtimeInspectorFields({ state: "completed", conversationId: "c-1", messages })
    expect(turn.map((f) => [f.label, f.value])).toEqual([
      ["Status", "Completed"],
      ["Conversation", "c-1"],
      ["Last reply", "a-1"],
    ])
    expect(result).toEqual([])
    expect(task).toEqual([])
  })

  it("says the conversation is not saved rather than inventing an id", () => {
    const { turn } = runtimeInspectorFields({ state: "failed", conversationId: null, messages: [] })
    expect(turn.find((f) => f.label === "Conversation")?.value).toBe("Not saved yet")
    expect(turn.find((f) => f.label === "Last reply")).toBeUndefined()
  })

  it("reports partial step counts from the execution result", () => {
    const { result } = runtimeInspectorFields({
      state: "partial",
      conversationId: "c-1",
      messages,
      executionResult: {
        success: true,
        task_label: "Sync contacts",
        structured: { stepBreakdown: [{ success: true }, { success: false }] },
      } as never,
    })
    expect(result.find((f) => f.label === "Steps")?.value).toBe("1 of 2 finished")
    expect(result.find((f) => f.label === "Outcome")?.value).toBe("Succeeded")
  })

  it("renders no Details control while idle or live", () => {
    root = createRoot(container)
    act(() => root!.render(createElement(GravitreAIRuntimeDetails, { state: "streaming", messages })))
    expect(container.querySelector("[data-gravitre-ai-runtime-details]")).toBeNull()
    act(() => root!.render(createElement(GravitreAIRuntimeDetails, { state: "idle", messages })))
    expect(container.querySelector("[data-gravitre-ai-runtime-state]")).toBeNull()
  })

  it("renders a Details control for settled states", () => {
    root = createRoot(container)
    act(() => root!.render(createElement(GravitreAIRuntimeDetails, { state: "completed", conversationId: "c-1", messages })))
    expect(container.querySelector("[data-gravitre-ai-runtime-details]")?.textContent).toBe("Details")
  })
})
