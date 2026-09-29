// @vitest-environment jsdom
/**
 * Slice 1 — the real float bridge inside the real provider across window modes.
 *
 * Mutation-proof in the same sense as ai-workspace-float-bridge.test.ts: the
 * transcript/composer must receive the SAME `messages` array and `onSubmit`
 * function through compact → docked → floating, and the transcript must never
 * unmount (a remount would reset scroll/voice state even with identical props).
 */
import { act, createElement, useEffect } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useParams: () => ({}),
}))

const calls = {
  transcript: [] as Array<Record<string, unknown>>,
  composer: [] as Array<Record<string, unknown>>,
  window: [] as Array<Record<string, unknown>>,
  transcriptMounts: 0,
}

vi.mock("@/components/gravitre/ai-conversation-core", () => ({
  GravitreAIConversationTranscript: (props: Record<string, unknown>) => {
    calls.transcript.push(props)
    useEffect(() => {
      calls.transcriptMounts += 1
    }, [])
    return null
  },
  GravitreAIConversationComposer: (props: Record<string, unknown>) => {
    calls.composer.push(props)
    return null
  },
}))
vi.mock("@/components/gravitre/ai-context-indicator", () => ({ GravitreAIContextIndicator: () => null }))
vi.mock("@/components/gravitre/ai-floating-workspace", () => ({
  GravitreFloatingWorkspace: (props: Record<string, unknown> & { children: unknown }) => {
    calls.window.push(props)
    return props.children
  },
}))

import { GravitreAIFloatBridge } from "@/app/ai/_components/ai-workspace-float-bridge"
import {
  GravitreAIWorkspaceProvider,
  useGravitreAIWorkspace,
  type GravitreAIWorkspaceContextValue,
} from "@/components/gravitre/ai-workspace-provider"
import { readWindowManagerPreference } from "@/lib/gravitre-window-manager"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  calls.transcript = []
  calls.composer = []
  calls.window = []
  calls.transcriptMounts = 0
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
const realOnSubmit = vi.fn()

function Harness({ sink }: { sink: { value: GravitreAIWorkspaceContextValue | null } }) {
  sink.value = useGravitreAIWorkspace()
  return createElement(GravitreAIFloatBridge, {
    presence: "ready",
    onClose: vi.fn(),
    messages: realMessages,
    status: "ready",
    conversationId: "conv-real-1",
    input: "",
    onInputChange: vi.fn(),
    onSubmit: realOnSubmit,
    canSubmit: false,
    voiceEntitled: false,
  })
}

function mount() {
  const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
  root = createRoot(container)
  act(() => {
    root!.render(createElement(GravitreAIWorkspaceProvider, null, createElement(Harness, { sink })))
  })
  return sink
}

describe("GravitreAIFloatBridge window modes (real provider)", () => {
  it("keeps the same conversation through compact → docked → floating without remounting", () => {
    const sink = mount()
    act(() => sink.value!.setPresentationMode("compact"))
    expect(calls.window.at(-1)).toMatchObject({ placement: "window", variant: "compact" })

    act(() => (calls.window.at(-1)!.onDock as () => void)())
    expect(sink.value!.presentationMode).toBe("docked")
    expect(calls.window.at(-1)).toMatchObject({ placement: "docked" })

    act(() => (calls.window.at(-1)!.onUndock as () => void)())
    expect(sink.value!.presentationMode).toBe("floating")
    expect(calls.window.at(-1)).toMatchObject({ placement: "window", variant: "floating" })

    for (const props of calls.transcript) {
      expect(props.messages).toBe(realMessages)
      expect(props.conversationId).toBe("conv-real-1")
    }
    for (const props of calls.composer) expect(props.onSubmit).toBe(realOnSubmit)
    expect(calls.transcriptMounts).toBe(1)
  })

  it("remembers an explicit dock/undock as the preference", () => {
    const sink = mount()
    act(() => sink.value!.setPresentationMode("compact"))
    act(() => (calls.window.at(-1)!.onDock as () => void)())
    expect(readWindowManagerPreference()).toBe("docked")
    act(() => (calls.window.at(-1)!.onUndock as () => void)())
    expect(readWindowManagerPreference()).toBe("floating")
  })

  it("renders no runtime status line when idle", () => {
    mount()
    expect(container.querySelector("[data-gravitre-ai-runtime-state]")).toBeNull()
  })
})
