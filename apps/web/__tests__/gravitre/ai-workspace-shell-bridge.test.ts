// @vitest-environment jsdom
/**
 * GravitreAIWorkspaceShellBridge — mutation-proof test, same technique as
 * __tests__/gravitre/ai-workspace-float-bridge.test.ts: asserts REFERENCE
 * IDENTITY (`toBe`) on the `messages` array, `conversations` array (left
 * panel), and `onSubmit` function — proving Expanded/Fullscreen render the
 * SAME conversation and the SAME conversation-sidebar data as Float/`/ai`,
 * not a lookalike/independent copy.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const stubCalls: {
  transcript: Array<Record<string, unknown>>
  composer: Array<Record<string, unknown>>
  leftPanel: Array<Record<string, unknown>>
  rightPanel: Array<Record<string, unknown>>
} = { transcript: [], composer: [], leftPanel: [], rightPanel: [] }

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
vi.mock("@/components/gravitre/ai-left-panel", () => ({
  GravitreAILeftPanel: (props: Record<string, unknown>) => {
    stubCalls.leftPanel.push(props)
    return null
  },
}))
vi.mock("@/components/gravitre/ai-right-panel", () => ({
  GravitreAIRightPanel: (props: Record<string, unknown>) => {
    stubCalls.rightPanel.push(props)
    return null
  },
}))
vi.mock("@/components/gravitre/ai-workspace-shell", () => ({
  GravitreAIWorkspaceShell: ({
    leftPanel,
    rightPanel,
    children,
  }: {
    leftPanel: unknown
    rightPanel: unknown
    children: unknown
  }) => {
    // Trivial passthrough so this test is not coupled to the shell's own
    // chrome/portal/focus-trap (covered separately in
    // ai-workspace-shell.test.ts) — it just needs to actually render its
    // slots so the mocked leaf components above get invoked.
    return [
      createElement("div", { key: "left" }, leftPanel as never),
      createElement("div", { key: "right" }, rightPanel as never),
      createElement("div", { key: "children" }, children as never),
    ]
  },
}))

import {
  GravitreAIWorkspaceShellBridge,
  type GravitreAIWorkspaceShellBridgeProps,
} from "@/app/ai/_components/ai-workspace-shell-bridge"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  stubCalls.transcript = []
  stubCalls.composer = []
  stubCalls.leftPanel = []
  stubCalls.rightPanel = []
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

function baseProps(
  overrides: Partial<GravitreAIWorkspaceShellBridgeProps> = {},
): GravitreAIWorkspaceShellBridgeProps {
  return {
    mode: "expanded",
    presence: "ready",
    onMinimizeToFloat: vi.fn(),
    onEnterFullscreen: vi.fn(),
    onExitFullscreen: vi.fn(),
    onClose: vi.fn(),
    leftCollapsed: false,
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
      isOpen: true,
      onToggle: vi.fn(),
    },
    rightCollapsed: false,
    onToggleRight: vi.fn(),
    rightPanelProps: {},
    liveActivityOpen: false,
    onToggleLiveActivity: vi.fn(),
    messages: [],
    status: "ready",
    input: "",
    onInputChange: vi.fn(),
    onSubmit: vi.fn(),
    canSubmit: false,
    voiceEntitled: false,
    ...overrides,
  }
}

describe("GravitreAIWorkspaceShellBridge — same-conversation proof", () => {
  it("forwards the exact same messages array reference to the transcript (not a copy)", () => {
    const realMessages = [{ id: "m1", role: "user" as const, parts: [] }]
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShellBridge, baseProps({ messages: realMessages, conversationId: "conv-real-1" })))
    })
    expect(stubCalls.transcript.length).toBeGreaterThanOrEqual(1)
    const forwarded = stubCalls.transcript.at(-1)!
    expect(forwarded.messages).toBe(realMessages)
    expect(forwarded.conversationId).toBe("conv-real-1")
  })

  it("forwards the exact same onSubmit/onInputChange function identity to the composer", () => {
    const realOnSubmit = vi.fn()
    const realOnInputChange = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceShellBridge,
          baseProps({ input: "draft", onSubmit: realOnSubmit, onInputChange: realOnInputChange, canSubmit: true }),
        ),
      )
    })
    const forwarded = stubCalls.composer.at(-1)!
    expect(forwarded.input).toBe("draft")
    expect(forwarded.onSubmit).toBe(realOnSubmit)
    expect(forwarded.onInputChange).toBe(realOnInputChange)
    ;(forwarded.onSubmit as () => void)()
    expect(realOnSubmit).toHaveBeenCalledTimes(1)
  })

  it("forwards the exact same conversations array reference to GravitreAILeftPanel", () => {
    // Only `id` matters for this reference-identity check — the mocked
    // GravitreAILeftPanel never reads the other Conversation fields, so a
    // partial shape is cast rather than constructing a full fixture.
    const realConversations = [{ id: "c1" }, { id: "c2" }] as unknown as GravitreAIWorkspaceShellBridgeProps["leftPanelProps"]["conversations"]
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceShellBridge,
          baseProps({
            leftPanelProps: { ...baseProps().leftPanelProps, conversations: realConversations },
          }),
        ),
      )
    })
    expect(stubCalls.leftPanel.length).toBeGreaterThanOrEqual(1)
    expect(stubCalls.leftPanel.at(-1)!.conversations).toBe(realConversations)
  })

  it("forwards pendingTask/progressSteps through to GravitreAIRightPanel unchanged", () => {
    const pendingTask = { title: "Reconnect HubSpot" } as never
    const progressSteps = ["step-1", "step-2"]
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceShellBridge,
          baseProps({ rightPanelProps: { pendingTask, progressSteps } }),
        ),
      )
    })
    const forwarded = stubCalls.rightPanel.at(-1)!
    expect(forwarded.pendingTask).toBe(pendingTask)
    expect(forwarded.progressSteps).toBe(progressSteps)
  })

  it("forwards liveActivityOpen/onToggleLiveActivity through to GravitreAIRightPanel", () => {
    const onToggleLiveActivity = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(GravitreAIWorkspaceShellBridge, baseProps({ liveActivityOpen: true, onToggleLiveActivity })),
      )
    })
    const forwarded = stubCalls.rightPanel.at(-1)!
    expect(forwarded.liveActivityOpen).toBe(true)
    expect(forwarded.onToggleLiveActivity).toBe(onToggleLiveActivity)
  })
})
