// @vitest-environment jsdom
/**
 * GravitreAIWorkspaceShell — Phase 3 Expanded/Fullscreen window shell.
 *
 * Covers B9's explicit accessibility asks:
 *  - Expanded: role="region", no aria-modal, Escape does nothing.
 *  - Fullscreen: role="dialog" aria-modal="true", real focus trap engaged
 *    on mount (first focusable gets focus), Escape calls onExitFullscreen.
 *  - Float's non-modal contract is verified separately in
 *    ai-floating-workspace.test.ts — this file only asserts THIS shell's
 *    own modal/non-modal split.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import {
  GravitreAIWorkspaceShell,
  type GravitreAIWorkspaceShellProps,
} from "@/components/gravitre/ai-workspace-shell"

let container: HTMLDivElement
let root: Root | null = null

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
  document.body.querySelectorAll("[data-gravitre-ai-shell]").forEach((el) => el.remove())
})

function baseProps(overrides: Partial<GravitreAIWorkspaceShellProps> = {}): GravitreAIWorkspaceShellProps {
  return {
    mode: "expanded",
    presence: "ready",
    leftPanel: createElement("button", { id: "left-btn" }, "left"),
    rightPanel: createElement("button", { id: "right-btn" }, "right"),
    leftCollapsed: false,
    onToggleLeft: vi.fn(),
    rightCollapsed: false,
    onToggleRight: vi.fn(),
    onMinimizeToFloat: vi.fn(),
    onEnterFullscreen: vi.fn(),
    onExitFullscreen: vi.fn(),
    onClose: vi.fn(),
    children: createElement("button", { id: "center-btn" }, "center"),
    ...overrides,
  }
}

describe("GravitreAIWorkspaceShell — Expanded mode", () => {
  it("portals to document.body with role='region', no aria-modal", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "expanded" })))
    })
    const shell = document.body.querySelector("[data-gravitre-ai-shell]")
    expect(shell).not.toBeNull()
    expect(shell?.getAttribute("role")).toBe("region")
    expect(shell?.getAttribute("aria-modal")).toBeNull()
    expect(shell?.getAttribute("data-gravitre-ai-shell-mode")).toBe("expanded")
  })

  it("Escape does nothing in Expanded mode (no modal semantics to escape from)", () => {
    const onExitFullscreen = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "expanded", onExitFullscreen })))
    })
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
    })
    expect(onExitFullscreen).not.toHaveBeenCalled()
  })

  it("renders an Expand ('Fullscreen') control that calls onEnterFullscreen, not onExitFullscreen", () => {
    const onEnterFullscreen = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "expanded", onEnterFullscreen })))
    })
    const button = document.body.querySelector(
      "[data-gravitre-ai-shell] button[aria-label='Fullscreen']",
    ) as HTMLButtonElement
    expect(button).toBeTruthy()
    act(() => {
      button.click()
    })
    expect(onEnterFullscreen).toHaveBeenCalledTimes(1)
  })
})

describe("GravitreAIWorkspaceShell — Fullscreen mode", () => {
  it("portals with role='dialog' aria-modal='true'", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "fullscreen" })))
    })
    const shell = document.body.querySelector("[data-gravitre-ai-shell]")
    expect(shell?.getAttribute("role")).toBe("dialog")
    expect(shell?.getAttribute("aria-modal")).toBe("true")
    expect(shell?.getAttribute("data-gravitre-ai-shell-mode")).toBe("fullscreen")
  })

  it("engages a real focus trap on mount — first focusable descendant receives focus", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "fullscreen" })))
    })
    // The shell's own header renders focusable buttons before `children`,
    // so the trap's "first focusable" is one of those, not our test button
    // — the important assertion is that focus landed SOMEWHERE inside the
    // portalled shell, proving the trap activated (see
    // use-focus-trap.test.ts for the detailed wrap-cycling proof).
    const shell = document.body.querySelector("[data-gravitre-ai-shell]") as HTMLElement
    expect(shell.contains(document.activeElement)).toBe(true)
  })

  it("Escape calls onExitFullscreen", () => {
    const onExitFullscreen = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "fullscreen", onExitFullscreen })))
    })
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
    })
    expect(onExitFullscreen).toHaveBeenCalledTimes(1)
  })

  it("renders an 'Exit fullscreen' control that calls onExitFullscreen", () => {
    const onExitFullscreen = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "fullscreen", onExitFullscreen })))
    })
    const button = document.body.querySelector(
      "[data-gravitre-ai-shell] button[aria-label='Exit fullscreen']",
    ) as HTMLButtonElement
    expect(button).toBeTruthy()
    act(() => {
      button.click()
    })
    expect(onExitFullscreen).toHaveBeenCalledTimes(1)
  })
})

describe("GravitreAIWorkspaceShell — shared window controls", () => {
  it("wires collapse-left/collapse-right/minimize-to-float/close to their callbacks", () => {
    const onToggleLeft = vi.fn()
    const onToggleRight = vi.fn()
    const onMinimizeToFloat = vi.fn()
    const onClose = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreAIWorkspaceShell,
          baseProps({ mode: "expanded", onToggleLeft, onToggleRight, onMinimizeToFloat, onClose }),
        ),
      )
    })
    const shell = document.body.querySelector("[data-gravitre-ai-shell]") as HTMLElement
    const click = (label: string) => {
      const btn = shell.querySelector(`button[aria-label='${label}']`) as HTMLButtonElement
      expect(btn).toBeTruthy()
      act(() => btn.click())
    }
    click("Hide conversation history")
    expect(onToggleLeft).toHaveBeenCalledTimes(1)
    click("Hide context panel")
    expect(onToggleRight).toHaveBeenCalledTimes(1)
    click("Collapse to floating window")
    expect(onMinimizeToFloat).toHaveBeenCalledTimes(1)
    // Was "Close to helper" here while the float window called the identical
    // action "Minimize to helper". One action needs one name, and nothing is
    // closed -- the window returns to the launcher with the conversation intact.
    click("Minimize to helper")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("does not render the left/right panel wrapper when collapsed flags are set for the right panel", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreAIWorkspaceShell, baseProps({ mode: "expanded", rightCollapsed: true })))
    })
    const shell = document.body.querySelector("[data-gravitre-ai-shell]") as HTMLElement
    expect(shell.querySelector("#right-btn")).toBeNull()
  })
})
