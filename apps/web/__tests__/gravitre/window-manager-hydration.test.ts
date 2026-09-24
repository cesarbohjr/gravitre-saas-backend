// @vitest-environment jsdom
/**
 * Slice 1 regression: Window Manager preference must not cause a hydration
 * mismatch. The server has no localStorage, so SSR always renders the contextual
 * default; the client must hydrate that same markup and apply the remembered
 * preference afterwards.
 *
 * The control case renders a component that reads localStorage during render
 * (the Slice 0 bug class) and asserts this harness DOES report a mismatch for it,
 * so the passing case is not vacuous.
 */
import { act, createElement, type ReactElement } from "react"
import { hydrateRoot, type Root } from "react-dom/client"
import { renderToString } from "react-dom/server"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GravitreWindowManagerShell } from "@/components/gravitre/window-manager/gravitre-window-manager-shell"
import { GRAVITRE_WM_PREFERENCE_STORAGE_KEY, writeWindowManagerPreference } from "@/lib/gravitre-window-manager"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
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
  vi.restoreAllMocks()
})

/** SSR with empty storage (as on the server), then seed, then hydrate. */
function ssrThenHydrate(element: ReactElement, seed: () => void): { recoverable: unknown[]; consoleErrors: string[] } {
  container.innerHTML = renderToString(element)
  seed()
  const recoverable: unknown[] = []
  const consoleErrors: string[] = []
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    consoleErrors.push(args.map(String).join(" "))
  })
  act(() => {
    root = hydrateRoot(container, element, {
      onRecoverableError: (error) => recoverable.push(error),
    })
  })
  return { recoverable, consoleErrors }
}

function activeMode(): string | null {
  const meta = Array.from(container.querySelectorAll("p")).find((p) => p.textContent?.includes("active:"))
  const strongs = meta?.querySelectorAll("strong")
  return strongs && strongs.length ? (strongs[strongs.length - 1]!.textContent ?? null) : null
}

describe("Window Manager preference hydration", () => {
  it("hydrates without mismatch and then applies the remembered preference", () => {
    const element = createElement(GravitreWindowManagerShell, { pathname: "/dashboard", viewportWidth: 1280 })
    const html = renderToString(element)
    expect(html).toContain('data-wm-mode-source="contextual"')

    const { recoverable, consoleErrors } = ssrThenHydrate(element, () => writeWindowManagerPreference("expanded"))

    expect(recoverable).toEqual([])
    expect(consoleErrors.filter((e) => /hydrat/i.test(e))).toEqual([])
    expect(activeMode()).toBe("expanded")
    expect(container.querySelector("[data-slice0-wm-shell]")?.getAttribute("data-wm-mode-source")).toBe("preference")
  })

  it("without a stored preference, stays on the contextual default", () => {
    const element = createElement(GravitreWindowManagerShell, { pathname: "/dashboard", viewportWidth: 1280 })
    const { recoverable } = ssrThenHydrate(element, () => {})
    expect(recoverable).toEqual([])
    expect(activeMode()).toBe("floating")
  })

  it("preference changes in another tab propagate after hydration", () => {
    const element = createElement(GravitreWindowManagerShell, { pathname: "/dashboard", viewportWidth: 1280 })
    ssrThenHydrate(element, () => {})
    act(() => {
      window.localStorage.setItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY, "docked")
      window.dispatchEvent(new StorageEvent("storage", { key: GRAVITRE_WM_PREFERENCE_STORAGE_KEY }))
    })
    expect(activeMode()).toBe("docked")
  })

  it("control: a render-time localStorage read IS reported as a mismatch by this harness", () => {
    function NaiveReader() {
      const stored = typeof window !== "undefined" ? window.localStorage.getItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY) : null
      return createElement("p", null, `active: ${stored ?? "floating"}`)
    }
    const { recoverable, consoleErrors } = ssrThenHydrate(createElement(NaiveReader), () =>
      window.localStorage.setItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY, "expanded"),
    )
    expect(recoverable.length + consoleErrors.filter((e) => /hydrat|did not match/i.test(e)).length).toBeGreaterThan(0)
  })
})
