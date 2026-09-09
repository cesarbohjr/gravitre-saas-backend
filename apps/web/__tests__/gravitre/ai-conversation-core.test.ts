// @vitest-environment jsdom
/**
 * GravitreAIConversation{Transcript,Composer} tests — Phase 1 extraction.
 *
 * `ChatTranscript` and `SharedChatComposerControls` are mocked to trivial
 * stubs here on purpose: this file is testing the EXTRACTION layer (does the
 * wrapper forward props unchanged, and does it publish into the shared
 * provider?), not re-testing those leaf components' own rendering, which is
 * out of scope for a pure state-hoisting refactor. Forwarding every prop
 * unchanged is exactly what "zero visible behavior change" requires: the
 * leaf components render byte-identical output either way.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock("next/navigation", () => ({
  usePathname: () => "/ai",
  useParams: () => ({}),
}))

vi.mock("@/components/gravitre/assistant/chat-transcript", () => ({
  ChatTranscript: (props: Record<string, unknown>) => {
    stubCalls.chatTranscript.push(props)
    return null
  },
}))

vi.mock("@/components/gravitre/assistant/shared-chat-composer-controls", () => ({
  SharedChatComposerControls: (props: Record<string, unknown>) => {
    stubCalls.composer.push(props)
    return null
  },
}))

const stubCalls: { chatTranscript: Array<Record<string, unknown>>; composer: Array<Record<string, unknown>> } = {
  chatTranscript: [],
  composer: [],
}

import {
  GravitreAIWorkspaceProvider,
  useGravitreAIWorkspace,
  type GravitreAIWorkspaceContextValue,
} from "@/components/gravitre/ai-workspace-provider"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  stubCalls.chatTranscript = []
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

function Probe({ sink }: { sink: { value: GravitreAIWorkspaceContextValue | null } }) {
  sink.value = useGravitreAIWorkspace()
  return null
}

describe("GravitreAIConversationTranscript", () => {
  it("forwards every ChatTranscript prop unchanged (mechanical extraction, no rendering change)", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceProvider,
          null,
          createElement(Probe, { sink }),
          createElement(GravitreAIConversationTranscript, {
            routeKey: "/ai",
            messages: [{ id: "m1", role: "user", parts: [] }],
            assistantLabel: "Gravitre",
            conversationId: "conv-1",
            conversationTitle: "Chat",
            status: "streaming",
            isStreaming: true,
            isBusy: true,
            dialogueMode: "execute",
          }),
        ),
      )
    })

    // The provider re-renders once its own state updates from the publish
    // effect below, so ChatTranscript may render more than once — assert on
    // the settled (last) call's props, not the render count.
    expect(stubCalls.chatTranscript.length).toBeGreaterThanOrEqual(1)
    const forwarded = stubCalls.chatTranscript.at(-1)!
    expect(forwarded.messages).toEqual([{ id: "m1", role: "user", parts: [] }])
    expect(forwarded.assistantLabel).toBe("Gravitre")
    expect(forwarded.conversationId).toBe("conv-1")
    expect(forwarded.dialogueMode).toBe("execute")
    // routeKey/conversationTitle/status/isBusy are provider-publish-only —
    // ChatTranscript never took them before, and must not receive them now.
    expect(forwarded.routeKey).toBeUndefined()
    expect(forwarded.conversationTitle).toBeUndefined()
    expect(forwarded.status).toBeUndefined()
    expect(forwarded.isBusy).toBeUndefined()
  })

  it("publishes a conversation + approval snapshot into the shared provider", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceProvider,
          null,
          createElement(Probe, { sink }),
          createElement(GravitreAIConversationTranscript, {
            routeKey: "/agents/[id]/chat",
            messages: [],
            conversationId: "conv-42",
            conversationTitle: "Agent chat",
            status: "streaming",
            isStreaming: true,
            isBusy: true,
            dialogueMode: "execute",
            pendingTask: { title: "Send email" } as never,
          }),
        ),
      )
    })

    expect(sink.value?.conversation).toMatchObject({
      routeKey: "/agents/[id]/chat",
      activeConversationId: "conv-42",
      conversationTitle: "Agent chat",
      status: "streaming",
      isStreaming: true,
      isBusy: true,
    })
    expect(sink.value?.approval?.dialogueMode).toBe("execute")
    expect(sink.value?.approval?.pendingTask).toEqual({ title: "Send email" })
  })
})

describe("GravitreAIConversationComposer", () => {
  it("forwards every SharedChatComposerControls prop unchanged", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    root = createRoot(container)
    const onInputChange = vi.fn()
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceProvider,
          null,
          createElement(Probe, { sink }),
          createElement(GravitreAIConversationComposer, {
            input: "hello",
            onInputChange,
            modality: "voice",
            voiceEntitled: true,
            voicePresence: "listening",
          }),
        ),
      )
    })

    expect(stubCalls.composer.length).toBeGreaterThanOrEqual(1)
    const forwarded = stubCalls.composer.at(-1)!
    expect(forwarded.input).toBe("hello")
    expect(forwarded.onInputChange).toBe(onInputChange)
    expect(forwarded.modality).toBe("voice")
    expect(forwarded.voicePresence).toBe("listening")
    // billingIssue is a provider-publish-only field, not a real composer prop.
    expect(forwarded.billingIssue).toBeUndefined()
  })

  it("publishes a voice snapshot into the shared provider", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceProvider,
          null,
          createElement(Probe, { sink }),
          createElement(GravitreAIConversationComposer, {
            input: "",
            onInputChange: () => {},
            modality: "voice",
            voiceEntitled: true,
            voicePresence: "speaking",
            voicePresenceDetail: "reading reply",
            voiceBilling: true,
          }),
        ),
      )
    })

    expect(sink.value?.voice).toEqual({
      modality: "voice",
      presence: "speaking",
      presenceDetail: "reading reply",
      billing: true,
    })
  })
})
