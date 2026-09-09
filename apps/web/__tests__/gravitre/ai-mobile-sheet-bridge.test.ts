// @vitest-environment jsdom
/**
 * GravitreAIMobileSheetBridge — mutation-proof test, same technique as
 * __tests__/gravitre/ai-workspace-float-bridge.test.ts: asserts REFERENCE
 * IDENTITY (`toBe`, not `toEqual`) on the `messages` array and the
 * `onSubmit`/`onInputChange` function props forwarded into
 * `GravitreAIConversationTranscript`/`GravitreAIConversationComposer` — the
 * SAME leaf components desktop's Float/Expanded/Fullscreen bridges use.
 *
 * This is the direct evidence for this phase's required test (a): "the
 * mobile sheet shares the same conversation state as desktop." A lookalike
 * implementation that reconstructed a new messages array or a fresh no-op
 * submit handler for mobile would fail this test even if it rendered
 * visually identical content.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const stubCalls: { transcript: Array<Record<string, unknown>>; composer: Array<Record<string, unknown>> } = {
  transcript: [],
  composer: [],
}

vi.mock("@/components/gravitre/ai-conversation-core", () => ({
  GravitreAIConversationTranscript: (props: Record<string, unknown>) => {
    stubCalls.transcript.push(props)
    return null
  },
  GravitreAIConversationComposer: (props: Record<string, unknown>) => {
    stubCalls.composer.push(props)
    return null
  },
}))
vi.mock("@/components/gravitre/ai-mobile-sheet", () => ({
  GravitreAIMobileSheet: ({ children }: { children: unknown }) => children,
}))

import { GravitreAIMobileSheetBridge } from "@/app/ai/_components/ai-mobile-sheet-bridge"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  stubCalls.transcript = []
  stubCalls.composer = []
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) {
    act(() => {
      root!.unmount()
    })
    root = null
  }
  container.remove()
})

describe("GravitreAIMobileSheetBridge — same-conversation proof (test requirement a)", () => {
  it("forwards the exact same messages array reference given by the /ai caller (not a copy)", () => {
    const realMessages = [{ id: "m1", role: "user" as const, parts: [] }]
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(GravitreAIMobileSheetBridge, {
          mode: "float",
          presence: "ready",
          onModeChange: vi.fn(),
          onClose: vi.fn(),
          messages: realMessages,
          status: "ready",
          conversationId: "conv-real-1",
          input: "",
          onInputChange: vi.fn(),
          onSubmit: vi.fn(),
          canSubmit: false,
          voiceEntitled: false,
        }),
      )
    })
    expect(stubCalls.transcript.length).toBeGreaterThanOrEqual(1)
    const forwarded = stubCalls.transcript.at(-1)!
    // Reference identity, not structural equality — this is the proof that
    // the mobile sheet is not a second, independent conversation instance.
    expect(forwarded.messages).toBe(realMessages)
    expect(forwarded.conversationId).toBe("conv-real-1")
  })

  it("forwards the exact same onSubmit/onInputChange function identity given by the /ai caller", () => {
    const realOnSubmit = vi.fn()
    const realOnInputChange = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(GravitreAIMobileSheetBridge, {
          mode: "expanded",
          presence: "ready",
          onModeChange: vi.fn(),
          onClose: vi.fn(),
          messages: [],
          status: "ready",
          input: "draft text",
          onInputChange: realOnInputChange,
          onSubmit: realOnSubmit,
          canSubmit: true,
          voiceEntitled: false,
        }),
      )
    })
    expect(stubCalls.composer.length).toBeGreaterThanOrEqual(1)
    const forwarded = stubCalls.composer.at(-1)!
    expect(forwarded.input).toBe("draft text")
    expect(forwarded.onSubmit).toBe(realOnSubmit)
    expect(forwarded.onInputChange).toBe(realOnInputChange)

    // Invoking the forwarded handler proves it reaches the real caller
    // function, not a mobile-only stand-in.
    ;(forwarded.onSubmit as () => void)()
    expect(realOnSubmit).toHaveBeenCalledTimes(1)
  })

  it("passes conversation approval state (pendingTask/executionResult) through unchanged, matching desktop's bridges", () => {
    const pendingTask = { title: "Reconnect HubSpot" } as never
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(GravitreAIMobileSheetBridge, {
          mode: "fullscreen",
          presence: "needs_approval",
          onModeChange: vi.fn(),
          onClose: vi.fn(),
          messages: [],
          status: "ready",
          dialogueMode: "execute",
          pendingTask,
          input: "",
          onInputChange: vi.fn(),
          onSubmit: vi.fn(),
          canSubmit: false,
          voiceEntitled: false,
        }),
      )
    })
    const forwarded = stubCalls.transcript.at(-1)!
    expect(forwarded.pendingTask).toBe(pendingTask)
    expect(forwarded.dialogueMode).toBe("execute")
  })
})
