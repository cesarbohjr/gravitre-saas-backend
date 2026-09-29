// @vitest-environment jsdom
/**
 * Slice 1 — Conversation / Work / Split in the expanded shell bridge, and the
 * runtime status line. Composition is presentation only: the transcript stays
 * mounted (hidden) in Work view and still receives the same messages array.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const calls = { transcript: [] as Array<Record<string, unknown>>, canvas: 0 }

vi.mock("@/components/gravitre/ai-conversation-core", () => ({
  GravitreAIConversationTranscript: (props: Record<string, unknown>) => {
    calls.transcript.push(props)
    return createElement("div", { "data-stub": "transcript" })
  },
  GravitreAIConversationComposer: () => null,
}))
vi.mock("@/components/gravitre/ai-left-panel", () => ({ GravitreAILeftPanel: () => null }))
vi.mock("@/components/gravitre/ai-right-panel", () => ({ GravitreAIRightPanel: () => null }))
vi.mock("@/components/gravitre/ai-context-indicator", () => ({ GravitreAIContextIndicator: () => null }))
vi.mock("@/components/gravitre/ai-work-canvas", () => ({
  GravitreAIWorkCanvas: () => {
    calls.canvas += 1
    return createElement("div", { "data-stub": "canvas" })
  },
}))
vi.mock("@/components/gravitre/ai-workspace-shell", () => ({
  GravitreAIWorkspaceShell: ({ headerAccessory, children }: { headerAccessory: unknown; children: unknown }) => [
    createElement("div", { key: "header" }, headerAccessory as never),
    createElement("div", { key: "body" }, children as never),
  ],
}))

import {
  GravitreAIWorkspaceShellBridge,
  type GravitreAIWorkspaceShellBridgeProps,
} from "@/app/ai/_components/ai-workspace-shell-bridge"
import { writeCompositionPreference } from "@/lib/gravitre-ai-composition"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  calls.transcript = []
  calls.canvas = 0
  window.localStorage.clear()
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) {
    act(() => root!.unmount())
    root = null
  }
  container.remove()
  window.localStorage.clear()
})

const realMessages = [{ id: "m1", role: "user" as const, parts: [] }]

function props(overrides: Partial<GravitreAIWorkspaceShellBridgeProps> = {}): GravitreAIWorkspaceShellBridgeProps {
  return {
    mode: "expanded",
    presence: "ready",
    onMinimizeToFloat: vi.fn(),
    onEnterFullscreen: vi.fn(),
    onExitFullscreen: vi.fn(),
    onClose: vi.fn(),
    leftCollapsed: true,
    onToggleLeft: vi.fn(),
    leftPanelProps: {
      conversations: [],
      activeConversationId: null,
      onSelect: vi.fn(),
      onNew: vi.fn(),
      onDelete: vi.fn(),
      onArchive: vi.fn(),
      onRename: vi.fn(),
      onBulkDelete: vi.fn(),
      isOpen: false,
      onToggle: vi.fn(),
    },
    rightCollapsed: true,
    onToggleRight: vi.fn(),
    rightPanelProps: {},
    liveActivityOpen: false,
    onToggleLiveActivity: vi.fn(),
    messages: realMessages,
    status: "ready",
    input: "",
    onInputChange: vi.fn(),
    onSubmit: vi.fn(),
    canSubmit: false,
    voiceEntitled: false,
    ...overrides,
  }
}

function render(p: GravitreAIWorkspaceShellBridgeProps) {
  root = createRoot(container)
  act(() => root!.render(createElement(GravitreAIWorkspaceShellBridge, p)))
}

const body = () => container.querySelector("[data-gravitre-ai-composition-body]")
const transcriptWrapper = () => container.querySelector('[data-stub="transcript"]')!.parentElement!

describe("composition", () => {
  it("is Conversation with Work/Split disabled when there is no work", () => {
    render(props())
    expect(body()?.getAttribute("data-gravitre-ai-composition-body")).toBe("conversation")
    const buttons = Array.from(container.querySelectorAll('[role="group"] button, [role="radiogroup"] button'))
    const disabled = buttons.filter((b) => b.hasAttribute("disabled")).map((b) => b.textContent)
    expect(disabled).toEqual(expect.arrayContaining(["Work", "Split"]))
    expect(calls.canvas).toBe(0)
  })

  it("defaults to Split when real work exists", () => {
    render(props({ executionResult: { success: true, title: "Created contact" } }))
    expect(body()?.getAttribute("data-gravitre-ai-composition-body")).toBe("split")
    expect(calls.canvas).toBeGreaterThan(0)
  })

  it("Work hides the transcript without unmounting it and keeps the same messages array", () => {
    writeCompositionPreference("work")
    render(props({ executionResult: { success: true, title: "Created contact" } }))
    expect(body()?.getAttribute("data-gravitre-ai-composition-body")).toBe("work")
    expect(transcriptWrapper().hidden).toBe(true)
    expect(calls.transcript.at(-1)!.messages).toBe(realMessages)
  })

  it("never hides a visible approval: Work falls back to Split", () => {
    writeCompositionPreference("work")
    render(
      props({
        dialogueMode: "confirm",
        canApprove: true,
        pendingTask: { type: "connector_action", status: "awaiting_confirm" },
      }),
    )
    expect(body()?.getAttribute("data-gravitre-ai-composition-body")).toBe("split")
    expect(transcriptWrapper().hidden).toBe(false)
    expect(container.querySelector("[data-gravitre-ai-runtime-state]")?.getAttribute("data-gravitre-ai-runtime-state")).toBe(
      "needs_approval",
    )
  })

  it("choosing a composition is remembered and re-renders from the store", () => {
    render(props({ executionResult: { success: true, title: "Created contact" } }))
    const conversationButton = Array.from(container.querySelectorAll("button")).find((b) => b.textContent === "Conversation")!
    act(() => conversationButton.click())
    expect(window.localStorage.getItem("gravitre.ai.composition.v1")).toBe("conversation")
    expect(body()?.getAttribute("data-gravitre-ai-composition-body")).toBe("conversation")
  })
})
