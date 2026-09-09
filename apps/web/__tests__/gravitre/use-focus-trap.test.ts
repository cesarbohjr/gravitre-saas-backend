// @vitest-environment jsdom
/**
 * useFocusTrap — Phase 3 (B9: "Fullscreen mode ... WITH a focus trap ...
 * confirmed via a test that tabbing cycles within it").
 */
import { act, createElement, useRef } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { useFocusTrap } from "@/hooks/use-focus-trap"

let container: HTMLDivElement
let root: Root | null = null

function Harness({ active }: { active: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  useFocusTrap(containerRef, active)
  return createElement(
    "div",
    null,
    createElement("button", { id: "outside" }, "outside"),
    createElement(
      "div",
      { ref: containerRef, tabIndex: -1, id: "trap-container" },
      createElement("button", { id: "first" }, "first"),
      createElement("button", { id: "last" }, "last"),
    ),
  )
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
})

describe("useFocusTrap", () => {
  it("does nothing while inactive", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(Harness, { active: false }))
    })
    const outside = container.querySelector("#outside") as HTMLButtonElement
    outside.focus()
    expect(document.activeElement).toBe(outside)
  })

  it("focuses the first focusable element on activation and remembers the prior focus", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(Harness, { active: false }))
    })
    const outside = container.querySelector("#outside") as HTMLButtonElement
    outside.focus()
    expect(document.activeElement).toBe(outside)

    act(() => {
      root!.render(createElement(Harness, { active: true }))
    })
    const first = container.querySelector("#first") as HTMLButtonElement
    expect(document.activeElement).toBe(first)
  })

  it("Tab on the last item wraps focus to the first item (real cycling, not just visual)", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(Harness, { active: true }))
    })
    const trapContainer = container.querySelector("#trap-container") as HTMLDivElement
    const first = container.querySelector("#first") as HTMLButtonElement
    const last = container.querySelector("#last") as HTMLButtonElement

    last.focus()
    expect(document.activeElement).toBe(last)

    act(() => {
      trapContainer.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }))
    })
    expect(document.activeElement).toBe(first)
  })

  it("Shift+Tab on the first item wraps focus to the last item", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(Harness, { active: true }))
    })
    const trapContainer = container.querySelector("#trap-container") as HTMLDivElement
    const first = container.querySelector("#first") as HTMLButtonElement
    const last = container.querySelector("#last") as HTMLButtonElement

    first.focus()
    expect(document.activeElement).toBe(first)

    act(() => {
      trapContainer.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true }),
      )
    })
    expect(document.activeElement).toBe(last)
  })

  it("restores focus to the previously-focused element on deactivation", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(Harness, { active: false }))
    })
    const outside = container.querySelector("#outside") as HTMLButtonElement
    outside.focus()

    act(() => {
      root!.render(createElement(Harness, { active: true }))
    })
    expect(document.activeElement).toBe(container.querySelector("#first"))

    act(() => {
      root!.render(createElement(Harness, { active: false }))
    })
    expect(document.activeElement).toBe(outside)
  })
})
