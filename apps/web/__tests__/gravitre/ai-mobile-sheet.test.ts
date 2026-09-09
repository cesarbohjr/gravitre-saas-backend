// @vitest-environment jsdom
/**
 * GravitreAIMobileSheet — Phase 4 mobile shell built on `vaul`.
 *
 * Covers this shell's own chrome (portal, header, presence pill, mode
 * controls) with arbitrary mock children — proving conversation identity
 * is NOT this file's job is exactly the point (see
 * ai-mobile-sheet-bridge.test.ts for the mutation-proof conversation test,
 * mirroring how ai-floating-workspace.test.ts / ai-workspace-float-bridge
 * .test.ts split the same concern for desktop Float).
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import {
  GravitreAIMobileSheet,
  type GravitreAIMobileSheetProps,
} from "@/components/gravitre/ai-mobile-sheet"

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
  document.body.querySelectorAll("[data-gravitre-mobile-sheet]").forEach((el) => el.remove())
  document.body.querySelectorAll("[data-gravitre-mobile-sheet-overlay]").forEach((el) => el.remove())
})

function baseProps(overrides: Partial<GravitreAIMobileSheetProps> = {}): GravitreAIMobileSheetProps {
  return {
    mode: "float",
    presence: "ready",
    onModeChange: vi.fn(),
    onClose: vi.fn(),
    children: createElement("div", { "data-testid": "sheet-body" }, "hello from mobile sheet"),
    ...overrides,
  }
}

function render(props: Partial<GravitreAIMobileSheetProps> = {}) {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(GravitreAIMobileSheet, baseProps(props)))
  })
}

describe("GravitreAIMobileSheet — float/expanded (non-modal snap points)", () => {
  it("portals its content to document.body, rendering the given children", () => {
    render()
    expect(container.querySelector("[data-testid='sheet-body']")).toBeNull()
    const portaled = document.body.querySelector("[data-gravitre-mobile-sheet]")
    expect(portaled).not.toBeNull()
    expect(portaled?.querySelector("[data-testid='sheet-body']")?.textContent).toBe("hello from mobile sheet")
  })

  it("tags the content with the current mode for snap-point verification", () => {
    render({ mode: "expanded" })
    const portaled = document.body.querySelector("[data-gravitre-mobile-sheet]")
    expect(portaled?.getAttribute("data-gravitre-mobile-sheet-mode")).toBe("expanded")
  })

  it("shows the given presence label in the header", () => {
    render({ presence: "needs_approval" })
    const portaled = document.body.querySelector("[data-gravitre-mobile-sheet]")
    expect(portaled?.textContent).toContain("Needs approval")
  })

  it("renders the drag handle (vaul's native gesture affordance) at float/expanded, not fullscreen", () => {
    render({ mode: "float" })
    expect(document.body.querySelector("[data-gravitre-mobile-sheet-handle]")).not.toBeNull()
  })

  it("does not render a backdrop overlay at float/expanded — not a modal, by construction (B1/B9)", () => {
    render({ mode: "float" })
    expect(document.body.querySelector("[data-gravitre-mobile-sheet-overlay]")).toBeNull()
  })

  it("renders an 'Expand' control at float that calls onModeChange('expanded')", () => {
    const onModeChange = vi.fn()
    render({ mode: "float", onModeChange })
    const button = document.body.querySelector(
      "[data-gravitre-mobile-sheet] button[aria-label='Expand']",
    ) as HTMLButtonElement
    expect(button).toBeTruthy()
    act(() => button.click())
    expect(onModeChange).toHaveBeenCalledWith("expanded")
  })

  it("does not render a 'Collapse to floating window' control at float (nothing below float except close)", () => {
    render({ mode: "float" })
    expect(
      document.body.querySelector("[data-gravitre-mobile-sheet] button[aria-label='Collapse to floating window']"),
    ).toBeNull()
  })

  it("calls onClose when 'Minimize to helper' is clicked", () => {
    const onClose = vi.fn()
    render({ mode: "float", onClose })
    const button = document.body.querySelector(
      "[data-gravitre-mobile-sheet] button[aria-label='Minimize to helper']",
    ) as HTMLButtonElement
    expect(button).toBeTruthy()
    act(() => button.click())
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("at expanded, renders both 'Collapse to floating window' and 'Fullscreen' controls", () => {
    const onModeChange = vi.fn()
    render({ mode: "expanded", onModeChange })
    const collapseBtn = document.body.querySelector(
      "[data-gravitre-mobile-sheet] button[aria-label='Collapse to floating window']",
    ) as HTMLButtonElement
    const fullscreenBtn = document.body.querySelector(
      "[data-gravitre-mobile-sheet] button[aria-label='Fullscreen']",
    ) as HTMLButtonElement
    expect(collapseBtn).toBeTruthy()
    expect(fullscreenBtn).toBeTruthy()
    act(() => collapseBtn.click())
    expect(onModeChange).toHaveBeenCalledWith("float")
    act(() => fullscreenBtn.click())
    expect(onModeChange).toHaveBeenCalledWith("fullscreen")
  })
})

describe("GravitreAIMobileSheet — fullscreen (modal snap point)", () => {
  it("renders a backdrop overlay at fullscreen (the one state that IS modal, matching desktop Fullscreen)", () => {
    render({ mode: "fullscreen" })
    expect(document.body.querySelector("[data-gravitre-mobile-sheet-overlay]")).not.toBeNull()
  })

  it("does not render the drag handle at fullscreen", () => {
    render({ mode: "fullscreen" })
    expect(document.body.querySelector("[data-gravitre-mobile-sheet-handle]")).toBeNull()
  })

  it("renders 'Exit fullscreen' (not 'Fullscreen') and no 'Expand' control", () => {
    render({ mode: "fullscreen" })
    expect(
      document.body.querySelector("[data-gravitre-mobile-sheet] button[aria-label='Exit fullscreen']"),
    ).not.toBeNull()
    expect(document.body.querySelector("[data-gravitre-mobile-sheet] button[aria-label='Expand']")).toBeNull()
    expect(document.body.querySelector("[data-gravitre-mobile-sheet] button[aria-label='Fullscreen']")).toBeNull()
  })

  it("'Exit fullscreen' calls onModeChange('expanded'), not onClose", () => {
    const onModeChange = vi.fn()
    const onClose = vi.fn()
    render({ mode: "fullscreen", onModeChange, onClose })
    const button = document.body.querySelector(
      "[data-gravitre-mobile-sheet] button[aria-label='Exit fullscreen']",
    ) as HTMLButtonElement
    act(() => button.click())
    expect(onModeChange).toHaveBeenCalledWith("expanded")
    expect(onClose).not.toHaveBeenCalled()
  })

  it("engages a real focus trap on mount (useFocusTrap, `active=isFullscreen`) — focus lands inside the sheet", () => {
    render({ mode: "fullscreen" })
    const sheet = document.body.querySelector("[data-gravitre-mobile-sheet]") as HTMLElement
    expect(sheet.contains(document.activeElement)).toBe(true)
  })
})
