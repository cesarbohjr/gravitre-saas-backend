// @vitest-environment jsdom
/**
 * useWindowResize — Phase 3 (B5 resize, B9 keyboard-operable, B10
 * rAF-throttled pointer handling).
 *
 * No @testing-library/react in this repo (confirmed in Phase 1) — this
 * follows the same react-dom/client + act pattern established in
 * __tests__/gravitre/ai-workspace-provider.test.ts.
 */
import { act, createElement, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { useWindowResize, type WindowSize } from "@/hooks/use-window-resize"

// This repo's jsdom version doesn't implement the global `PointerEvent`
// constructor (confirmed: `ReferenceError: PointerEvent is not defined`).
// The hook under test only reads `clientX`/`clientY` off the event and both
// React's synthetic `onPointerDown` and a raw `window.addEventListener`
// dispatch purely on the event `type` string, not an `instanceof` check — so
// a plain `MouseEvent` constructed with `type: "pointerdown"` etc. is
// observably identical for this test's purposes. Falls back to the real
// `PointerEvent` if a future jsdom upgrade adds it, so this isn't masking a
// real gap once the environment catches up.
const PointerEventCtor: typeof MouseEvent =
  typeof PointerEvent !== "undefined" ? (PointerEvent as unknown as typeof MouseEvent) : MouseEvent

const MIN: WindowSize = { width: 400, height: 420 }
const MAX: WindowSize = { width: 720, height: 760 }
const DEFAULT: WindowSize = { width: 520, height: 560 }

let container: HTMLDivElement
let root: Root | null = null
let lastSize: WindowSize = DEFAULT

function Harness() {
  const [size, setSize] = useState<WindowSize>(DEFAULT)
  lastSize = size
  const { onPointerDown, onKeyDown } = useWindowResize({
    size,
    min: MIN,
    max: MAX,
    onResize: setSize,
  })
  return createElement("div", {
    "data-testid": "handle",
    tabIndex: 0,
    onPointerDown,
    onKeyDown,
  })
}

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
  lastSize = DEFAULT
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

function mount() {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(Harness))
  })
}

describe("useWindowResize — keyboard", () => {
  it("ArrowRight grows width by the default step (16px)", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    act(() => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }))
    })
    expect(lastSize.width).toBe(DEFAULT.width + 16)
    expect(lastSize.height).toBe(DEFAULT.height)
  })

  it("ArrowUp shrinks height by the default step", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    act(() => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true, cancelable: true }))
    })
    expect(lastSize.height).toBe(DEFAULT.height - 16)
  })

  it("Shift+ArrowRight uses the coarser step (3x)", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    act(() => {
      handle.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight", shiftKey: true, bubbles: true, cancelable: true }),
      )
    })
    expect(lastSize.width).toBe(DEFAULT.width + 16 * 3)
  })

  it("clamps at the minimum width — repeated ArrowLeft never goes below min.width", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    for (let i = 0; i < 30; i++) {
      act(() => {
        handle.dispatchEvent(
          new KeyboardEvent("keydown", { key: "ArrowLeft", shiftKey: true, bubbles: true, cancelable: true }),
        )
      })
    }
    expect(lastSize.width).toBe(MIN.width)
  })

  it("clamps at the maximum height — repeated ArrowDown never exceeds max.height", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    for (let i = 0; i < 30; i++) {
      act(() => {
        handle.dispatchEvent(
          new KeyboardEvent("keydown", { key: "ArrowDown", shiftKey: true, bubbles: true, cancelable: true }),
        )
      })
    }
    expect(lastSize.height).toBe(MAX.height)
  })

  it("ignores unrelated keys", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    act(() => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }))
    })
    expect(lastSize).toEqual(DEFAULT)
  })
})

describe("useWindowResize — pointer drag", () => {
  it("resizes on pointer drag and flushes the final size synchronously on pointerup (no dangling rAF)", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    const rafSpy = vi.spyOn(window, "requestAnimationFrame")

    act(() => {
      handle.dispatchEvent(
        new PointerEventCtor("pointerdown", { clientX: 100, clientY: 100, bubbles: true, cancelable: true }),
      )
    })
    act(() => {
      window.dispatchEvent(new PointerEventCtor("pointermove", { clientX: 160, clientY: 130 }))
    })
    // Pending update is rAF-scheduled, not yet applied via setState.
    expect(rafSpy).toHaveBeenCalled()

    act(() => {
      window.dispatchEvent(new PointerEventCtor("pointerup", { clientX: 160, clientY: 130 }))
    })

    // pointerup cancels the pending rAF and flushes synchronously — the
    // final size reflects the full drag delta, not zero.
    expect(lastSize.width).toBe(DEFAULT.width + 60)
    expect(lastSize.height).toBe(DEFAULT.height + 30)
    rafSpy.mockRestore()
  })

  it("clamps pointer-drag results to min/max", () => {
    mount()
    const handle = container.querySelector("[data-testid='handle']") as HTMLDivElement
    act(() => {
      handle.dispatchEvent(
        new PointerEventCtor("pointerdown", { clientX: 100, clientY: 100, bubbles: true, cancelable: true }),
      )
    })
    act(() => {
      window.dispatchEvent(new PointerEventCtor("pointermove", { clientX: 100 + 5000, clientY: 100 + 5000 }))
    })
    act(() => {
      window.dispatchEvent(new PointerEventCtor("pointerup", { clientX: 100 + 5000, clientY: 100 + 5000 }))
    })
    expect(lastSize.width).toBe(MAX.width)
    expect(lastSize.height).toBe(MAX.height)
  })
})
