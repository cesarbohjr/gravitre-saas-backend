// @vitest-environment jsdom
/**
 * useGravitreMobileViewport — Phase 4 (B7 desktop↔mobile-sheet cutover).
 *
 * Confirms the hook reads the SAME `md` breakpoint (768px / `max-width:
 * 767px`) already governing MobileBottomNav/ConversationSidebar's drawer
 * mode elsewhere in this codebase, rather than inventing a new one, and
 * reacts to `matchMedia` "change" events (both the modern
 * addEventListener/removeEventListener API and the deprecated
 * addListener/removeListener Safari<14 fallback).
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { useGravitreMobileViewport } from "@/hooks/use-gravitre-mobile-viewport"

let container: HTMLDivElement
let root: Root | null = null
const lastValue = { current: false }

function Harness() {
  const isMobile = useGravitreMobileViewport()
  lastValue.current = isMobile
  return null
}

function render() {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(Harness))
  })
}

/** Minimal MediaQueryList mock supporting both listener registration styles. */
function makeMql(initialMatches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  const mql = {
    matches: initialMatches,
    media: "(max-width: 767px)",
    addEventListener: vi.fn((_type: string, cb: (event: MediaQueryListEvent) => void) => {
      listeners.add(cb)
    }),
    removeEventListener: vi.fn((_type: string, cb: (event: MediaQueryListEvent) => void) => {
      listeners.delete(cb)
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchListeners(matches: boolean) {
      mql.matches = matches
      listeners.forEach((cb) => cb({ matches } as MediaQueryListEvent))
    },
  }
  return mql
}

beforeEach(() => {
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
  vi.unstubAllGlobals()
})

describe("useGravitreMobileViewport — breakpoint reuse (B7)", () => {
  it("queries the same md breakpoint used elsewhere in this codebase: max-width: 767px (768px cutover)", () => {
    const matchMediaSpy = vi.fn((query: string) => makeMql(false))
    vi.stubGlobal("matchMedia", matchMediaSpy)
    render()
    expect(matchMediaSpy).toHaveBeenCalledWith("(max-width: 767px)")
  })

  it("returns true when the media query initially matches (viewport below 768px)", () => {
    vi.stubGlobal("matchMedia", () => makeMql(true))
    render()
    expect(lastValue.current).toBe(true)
  })

  it("returns false when the media query initially does not match (viewport at/above 768px)", () => {
    vi.stubGlobal("matchMedia", () => makeMql(false))
    render()
    expect(lastValue.current).toBe(false)
  })

  it("reacts live to a matchMedia change event (modern addEventListener API)", () => {
    const mql = makeMql(false)
    vi.stubGlobal("matchMedia", () => mql)
    render()
    expect(lastValue.current).toBe(false)
    act(() => {
      mql.dispatchListeners(true)
    })
    expect(lastValue.current).toBe(true)
  })

  it("removes the change listener on unmount (no leaked subscriptions)", () => {
    const mql = makeMql(false)
    vi.stubGlobal("matchMedia", () => mql)
    render()
    expect(mql.addEventListener).toHaveBeenCalledWith("change", expect.any(Function))
    act(() => {
      root!.unmount()
    })
    root = null
    expect(mql.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function))
  })

  it("falls back to the deprecated addListener/removeListener API when addEventListener is unavailable (Safari <14)", () => {
    const listeners = new Set<(event: MediaQueryListEvent) => void>()
    const legacyMql = {
      matches: false,
      media: "(max-width: 767px)",
      addListener: vi.fn((cb: (event: MediaQueryListEvent) => void) => listeners.add(cb)),
      removeListener: vi.fn((cb: (event: MediaQueryListEvent) => void) => listeners.delete(cb)),
    }
    vi.stubGlobal("matchMedia", () => legacyMql)
    render()
    expect(legacyMql.addListener).toHaveBeenCalledWith(expect.any(Function))
    act(() => {
      root!.unmount()
    })
    root = null
    expect(legacyMql.removeListener).toHaveBeenCalledWith(expect.any(Function))
  })

  it("does not throw when window.matchMedia is unavailable (defensive guard) and returns false", () => {
    vi.stubGlobal("matchMedia", undefined)
    expect(() => render()).not.toThrow()
    expect(lastValue.current).toBe(false)
  })
})
