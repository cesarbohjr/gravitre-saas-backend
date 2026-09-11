// @vitest-environment jsdom

/**
 * Renders the shared controls on every surface and asserts the thing that
 * actually went wrong in production: that a visible chat surface always offers a
 * working way out. The model tests in __tests__/lib/chat-window-state.test.ts
 * prove the manifest; these prove the manifest reaches the DOM as real buttons
 * with real handlers.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { act } from "react"
import { ChatWindowControls } from "@/components/gravitre/chat-window-controls"
import {
  CHAT_WINDOW_CONTROL_LABELS,
  controlsForSurface,
  isExitControl,
  type ChatSurface,
} from "@/lib/chat-window-state"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const SURFACES: ChatSurface[] = ["float", "expanded", "fullscreen", "embedded"]

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) act(() => root!.unmount())
  root = null
  container.remove()
})

function renderSurface(surface: ChatSurface, handlers: Record<string, () => void>) {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(ChatWindowControls, { surface, handlers }))
  })
}

/** Every handler the surface's manifest asks for, each a spy. */
function spiesFor(surface: ChatSurface) {
  const handlers: Record<string, ReturnType<typeof vi.fn>> = {}
  for (const id of controlsForSurface(surface)) handlers[id] = vi.fn()
  return handlers
}

describe.each(SURFACES)("ChatWindowControls on the %s surface", (surface) => {
  it("renders every control in the manifest as a native button with an accessible name", () => {
    renderSurface(surface, spiesFor(surface))
    for (const id of controlsForSurface(surface)) {
      const btn = container.querySelector(`[data-chat-window-control='${id}']`)
      expect(btn, `${surface} is missing control ${id}`).toBeTruthy()
      // Native buttons, not clickable divs: keyboard operation and focus come free.
      expect(btn?.tagName).toBe("BUTTON")
      expect(btn?.getAttribute("aria-label")).toBe(CHAT_WINDOW_CONTROL_LABELS[id])
    }
  })

  it("renders at least one working exit control", () => {
    const handlers = spiesFor(surface)
    renderSurface(surface, handlers)

    const exitIds = controlsForSurface(surface).filter(isExitControl)
    expect(exitIds.length).toBeGreaterThan(0)

    for (const id of exitIds) {
      const btn = container.querySelector(`[data-chat-window-control='${id}']`) as HTMLButtonElement
      act(() => btn.click())
      expect(handlers[id], `${surface} exit ${id} did not fire`).toHaveBeenCalledTimes(1)
    }
  })

  it("renders no control it cannot actually perform", () => {
    // A button wired to nothing is worse than the missing control it replaced:
    // it looks like a way out and silently is not.
    renderSurface(surface, {})
    expect(container.querySelectorAll("[data-chat-window-control]")).toHaveLength(0)
  })
})

describe("surface-specific expectations", () => {
  it("fullscreen exposes both exit-fullscreen and a route back to the launcher", () => {
    const handlers = spiesFor("fullscreen")
    renderSurface("fullscreen", handlers)
    const exit = container.querySelector("[data-chat-window-control='exitFullscreen']") as HTMLButtonElement
    const min = container.querySelector("[data-chat-window-control='minimizeToHelper']") as HTMLButtonElement
    expect(exit).toBeTruthy()
    expect(min).toBeTruthy()
    act(() => exit.click())
    act(() => min.click())
    expect(handlers.exitFullscreen).toHaveBeenCalledTimes(1)
    expect(handlers.minimizeToHelper).toHaveBeenCalledTimes(1)
  })

  it("the embedded /ai surface can be turned into a real window", () => {
    // This surface shipped with no window controls at all, and /ai hides the
    // floating launcher, so it was a chat you could see and not leave.
    const handlers = spiesFor("embedded")
    renderSurface("embedded", handlers)
    const btn = container.querySelector("[data-chat-window-control='openAsFloat']") as HTMLButtonElement
    expect(btn).toBeTruthy()
    act(() => btn.click())
    expect(handlers.openAsFloat).toHaveBeenCalledTimes(1)
  })

  it("keeps surface-specific leading controls alongside the shared ones", () => {
    // The expanded shell's panel toggles live in the same group; consolidating
    // the window controls must not drop them.
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(ChatWindowControls, {
          surface: "expanded",
          handlers: spiesFor("expanded"),
          leading: createElement("button", { type: "button", "aria-label": "Hide context panel" }),
        }),
      )
    })
    expect(container.querySelector("button[aria-label='Hide context panel']")).toBeTruthy()
    expect(container.querySelector("[data-chat-window-control='minimizeToHelper']")).toBeTruthy()
  })
})
