// @vitest-environment jsdom
/**
 * Slice 1 — G-STRUCT A3 in the real provider: contextual default + remembered
 * preference for the launcher and summon paths.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState = { value: "/dashboard" }
vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
  useParams: () => ({}),
}))

import {
  GravitreAIWorkspaceProvider,
  useGravitreAIWorkspace,
  type GravitreAIWorkspaceContextValue,
} from "@/components/gravitre/ai-workspace-provider"
import { readWindowManagerPreference, writeWindowManagerPreference } from "@/lib/gravitre-window-manager"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/dashboard"
  window.localStorage.clear()
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1280 })
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

function Probe({ sink }: { sink: { value: GravitreAIWorkspaceContextValue | null } }) {
  sink.value = useGravitreAIWorkspace()
  return null
}

function mount() {
  const sink: { value: GravitreAIWorkspaceContextValue | null } = { value: null }
  root = createRoot(container)
  act(() => root!.render(createElement(GravitreAIWorkspaceProvider, null, createElement(Probe, { sink }))))
  return sink
}

describe("provider window preference", () => {
  it("first launcher open uses the contextual default (floating on an operating page)", () => {
    const sink = mount()
    act(() => sink.value!.restoreFromHelper())
    expect(sink.value!.floatWorkspaceOpen).toBe(true)
    expect(sink.value!.presentationMode).toBe("floating")
  })

  it("contextual default is docked on expert workspaces", () => {
    pathnameState.value = "/intelligence"
    const sink = mount()
    act(() => sink.value!.restoreFromHelper())
    expect(sink.value!.presentationMode).toBe("docked")
  })

  it("narrow viewports get compact regardless of preference", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 })
    const sink = mount()
    act(() => sink.value!.summonWorkspace())
    expect(sink.value!.presentationMode).toBe("float")
  })

  it("a remembered preference wins over the contextual default", () => {
    writeWindowManagerPreference("docked")
    const sink = mount()
    act(() => sink.value!.restoreFromHelper())
    expect(sink.value!.presentationMode).toBe("docked")
  })

  it("minimizing remembers the mode and the launcher returns to it", () => {
    const sink = mount()
    act(() => sink.value!.summonWorkspace({ presentation: "expanded" }))
    act(() => sink.value!.minimizeToHelper())
    expect(readWindowManagerPreference()).toBe("expanded")
    expect(sink.value!.floatWorkspaceOpen).toBe(false)
    act(() => sink.value!.restoreFromHelper())
    expect(sink.value!.presentationMode).toBe("expanded")
  })

  it("explicit summon presentation still wins (callers that ask for compact get compact)", () => {
    writeWindowManagerPreference("docked")
    const sink = mount()
    act(() => sink.value!.summonWorkspace({ presentation: "compact" }))
    expect(sink.value!.presentationMode).toBe("float")
  })

  it("choosePresentationMode applies and remembers", () => {
    const sink = mount()
    act(() => sink.value!.choosePresentationMode("docked"))
    expect(sink.value!.presentationMode).toBe("docked")
    expect(readWindowManagerPreference()).toBe("docked")
  })

  it("requests launcher focus once after minimizing, never on first load", () => {
    const sink = mount()
    expect(sink.value!.takeHelperFocusRequest()).toBe(false)
    act(() => sink.value!.summonWorkspace({ presentation: "expanded" }))
    act(() => sink.value!.minimizeToHelper())
    expect(sink.value!.takeHelperFocusRequest()).toBe(true)
    expect(sink.value!.takeHelperFocusRequest()).toBe(false)
    act(() => sink.value!.restoreFromHelper())
    expect(sink.value!.takeHelperFocusRequest()).toBe(false)
  })
})
