// @vitest-environment jsdom
/**
 * GravitreAIWorkspaceProvider tests — Phase 1 state-hoisting refactor.
 *
 * There is no @testing-library/react in this repo (confirmed absent from
 * node_modules before this change) and vitest.config.ts's `include` only
 * matches `*.test.ts`, not `.tsx` — adding a new test dependency mid-task was
 * avoided by writing these assertions directly against `react-dom/client` +
 * `react`'s `act`, which are already dependencies, using
 * `React.createElement` instead of JSX so the file can stay `.ts`.
 *
 * The most important test here (`does not remount across simulated route
 * navigation`) is the mutation-proof check the Phase 1 task explicitly
 * required: it would FAIL today if `GravitreAIWorkspaceProvider` were
 * accidentally mounted per-route instead of once at `app/layout.tsx`, and it
 * would also fail (proving the test isn't vacuous) if the provider really
 * were torn down and recreated.
 */
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { createElement } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

// React 19's act() warns unless the environment explicitly opts in — this
// repo has no @testing-library/react (which normally sets this), so it's set
// directly. jsdom (via the per-file `@vitest-environment jsdom` docblock
// above) is the only thing these tests need beyond what react-dom already
// ships with.
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState: { value: string } = { value: "/ai" }
const paramsState: { value: Record<string, string> } = { value: {} }

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
  useParams: () => paramsState.value,
}))

// Imported after the mock so the provider picks up the mocked navigation hooks.
import {
  GravitreAIWorkspaceProvider,
  useGravitreAIWorkspace,
  type GravitreAIWorkspaceContextValue,
} from "@/components/gravitre/ai-workspace-provider"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/ai"
  paramsState.value = {}
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

/** Renders a probe child that stashes the live context value into `sink`. */
function Probe({ sink }: { sink: { value: GravitreAIWorkspaceContextValue | null } }) {
  sink.value = useGravitreAIWorkspace()
  return null
}

function mount(sink: { value: GravitreAIWorkspaceContextValue | null }) {
  root = createRoot(container)
  act(() => {
    root!.render(
      createElement(GravitreAIWorkspaceProvider, null, createElement(Probe, { sink })),
    )
  })
}

describe("useGravitreAIWorkspace", () => {
  it("throws when used outside a GravitreAIWorkspaceProvider", () => {
    const badRoot = createRoot(container)
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    expect(() => {
      act(() => {
        badRoot.render(createElement(Probe, { sink }))
      })
    }).toThrow(/GravitreAIWorkspaceProvider/)
    act(() => {
      badRoot.unmount()
    })
  })

  it("defaults presentationMode to 'expanded' when not auto-opening /ai", () => {
    pathnameState.value = "/dashboard"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    expect(sink.value?.presentationMode).toBe("expanded")
    expect(sink.value?.floatWorkspaceOpen).toBe(false)
    expect(sink.value?.canonicalPresentation).toBe("minimized")
  })

  it("exposes pageContext from the current route, independent of conversation state", () => {
    pathnameState.value = "/agents/42/chat"
    paramsState.value = { id: "42" }
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    expect(sink.value?.pageContext.pathname).toBe("/agents/42/chat")
    expect(sink.value?.pageContext.params).toEqual({ id: "42" })
    expect(sink.value?.pageContext.selected).toBeNull()
    // Conversation must start untouched by pageContext.
    expect(sink.value?.conversation).toBeNull()
  })

  it(
    "auto-opens floatWorkspaceOpen on a direct /ai visit as fullscreen of the canonical workspace",
    () => {
      pathnameState.value = "/ai"
      const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
      mount(sink)
      expect(sink.value?.floatWorkspaceOpen).toBe(true)
      expect(sink.value?.presentationMode).toBe("fullscreen")
      expect(sink.value?.canonicalPresentation).toBe("fullscreen")
    },
  )

  it("does NOT auto-open floatWorkspaceOpen on a non-/ai route", () => {
    pathnameState.value = "/dashboard"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    expect(sink.value?.floatWorkspaceOpen).toBe(false)
  })

  it(
    "an explicit close sticks for the rest of the session — does not " +
      "immediately reopen on re-render while still on /ai",
    () => {
      const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
      mount(sink)
      expect(sink.value?.floatWorkspaceOpen).toBe(true) // auto-opened

      act(() => {
        sink.value!.setFloatWorkspaceOpen(false)
      })
      expect(sink.value?.floatWorkspaceOpen).toBe(false)

      // Force a re-render (e.g. an unrelated state publish) while still on
      // /ai — the auto-open effect must not fire again.
      act(() => {
        sink.value!.setPresentationMode("expanded")
      })
      expect(sink.value?.floatWorkspaceOpen).toBe(false)
    },
  )

  it("setFloatWorkspaceOpen updates state independently of presentationMode", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.setFloatWorkspaceOpen(true)
    })
    expect(sink.value?.floatWorkspaceOpen).toBe(true)
    expect(sink.value?.presentationMode).toBe("fullscreen")
  })

  it("setPresentationMode updates state without disturbing pageContext or conversation", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.setPresentationMode("float")
    })
    expect(sink.value?.presentationMode).toBe("float")
    expect(sink.value?.pageContext.pathname).toBe("/ai")
  })

  it("setConversation / setApproval / setVoice publish snapshots readable back via the hook", () => {
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.setConversation({
        routeKey: "/ai",
        activeConversationId: "conv-1",
        conversationTitle: "Chat",
        messages: [],
        status: "ready",
        isStreaming: false,
        isBusy: false,
      })
      sink.value!.setApproval({
        dialogueMode: "execute",
        pendingTask: null,
        executionResult: null,
        confirmExecuting: false,
      })
      sink.value!.setVoice({
        modality: "text",
        presence: "idle",
        billing: false,
      })
    })
    expect(sink.value?.conversation?.activeConversationId).toBe("conv-1")
    expect(sink.value?.approval?.dialogueMode).toBe("execute")
    expect(sink.value?.voice?.modality).toBe("text")
  })

  it(
    "does not remount across simulated route navigation (mutation-proof: " +
      "would fail if the provider were mounted per-route instead of once " +
      "at app/layout.tsx)",
    () => {
      const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
      mount(sink)
      const firstInstanceId = sink.value?.instanceId
      expect(firstInstanceId).toBeTruthy()

      // Simulate a route change: the provider keeps rendering (it is mounted
      // once in app/layout.tsx, above the per-page <AppShell>), but its
      // pathname-derived pageContext and child tree change underneath it.
      pathnameState.value = "/agents/42/chat"
      paramsState.value = { id: "42" }
      act(() => {
        root!.render(
          createElement(
            GravitreAIWorkspaceProvider,
            null,
            createElement("div", { key: "different-route-tree" }, createElement(Probe, { sink })),
          ),
        )
      })

      expect(sink.value?.instanceId).toBe(firstInstanceId)
      expect(sink.value?.pageContext.pathname).toBe("/agents/42/chat")
    },
  )

  it(
    "DOES change instanceId on a real unmount+remount (proves the identity " +
      "check above is not vacuous)",
    () => {
      const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
      mount(sink)
      const firstInstanceId = sink.value?.instanceId

      act(() => {
        root!.unmount()
      })
      root = createRoot(container)
      act(() => {
        root!.render(
          createElement(GravitreAIWorkspaceProvider, null, createElement(Probe, { sink })),
        )
      })

      expect(sink.value?.instanceId).toBeTruthy()
      expect(sink.value?.instanceId).not.toBe(firstInstanceId)
    },
  )

  it("maps compact onto the shipped float mode and reports canonicalPresentation", () => {
    pathnameState.value = "/dashboard"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    expect(sink.value?.canonicalPresentation).toBe("minimized")
    act(() => {
      sink.value!.setPresentationMode("compact")
      sink.value!.setFloatWorkspaceOpen(true)
    })
    expect(sink.value?.presentationMode).toBe("float")
    expect(sink.value?.canonicalPresentation).toBe("compact")
  })

  it("summonWorkspace opens compact over the current page with composer intent and selected entity", () => {
    pathnameState.value = "/intelligence"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.summonWorkspace({
        presentation: "compact",
        composerText: "What changed for Acme?",
        submit: true,
        selected: { kind: "entity", id: "acme", label: "Acme Corporation" },
        agentScope: null,
      })
    })
    expect(sink.value?.floatWorkspaceOpen).toBe(true)
    expect(sink.value?.presentationMode).toBe("float")
    expect(sink.value?.canonicalPresentation).toBe("compact")
    expect(sink.value?.pageContext.selected).toEqual({
      kind: "entity",
      id: "acme",
      label: "Acme Corporation",
    })
    expect(sink.value?.composerIntent?.text).toBe("What changed for Acme?")
    expect(sink.value?.composerIntent?.submit).toBe(true)
    expect(sink.value?.agentScope).toBeNull()
  })

  it("summonWorkspace can apply agent scope without creating a second runtime owner", () => {
    pathnameState.value = "/agents/42/chat"
    paramsState.value = { id: "42" }
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.summonWorkspace({
        presentation: "fullscreen",
        agentScope: { agentId: "42", name: "Lead Enrichment Coordinator" },
      })
    })
    expect(sink.value?.canonicalPresentation).toBe("fullscreen")
    expect(sink.value?.agentScope?.agentId).toBe("42")
    expect(sink.value?.agentScope?.name).toBe("Lead Enrichment Coordinator")
  })

  it("clears selected entity and agent scope when leaving the surface that set them", () => {
    pathnameState.value = "/intelligence"
    const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
    mount(sink)
    act(() => {
      sink.value!.summonWorkspace({
        presentation: "compact",
        selected: { kind: "entity", id: "acme", label: "Acme Corporation" },
        agentScope: { agentId: "sales", name: "Sales Agent" },
      })
    })
    expect(sink.value?.pageContext.selected?.id).toBe("acme")
    expect(sink.value?.agentScope?.agentId).toBe("sales")

    pathnameState.value = "/intelligence/performance"
    act(() => {
      root!.render(
        createElement(GravitreAIWorkspaceProvider, null, createElement(Probe, { sink })),
      )
    })
    expect(sink.value?.pageContext.selected).toBeNull()
    expect(sink.value?.agentScope).toBeNull()
    expect(sink.value?.canonicalPresentation).toBe("compact")
  })
})
