// @vitest-environment jsdom
/**
 * GravitreFloatingWorkspace — Phase 2 Float window shell. This file only
 * exercises the shell's own chrome (portal, header, presence pill, close
 * button) with arbitrary mock children — proving conversation identity is
 * NOT this file's job is exactly the point (see
 * ai-workspace-float-bridge.test.ts for the mutation-proof conversation
 * test, and ai-floating-workspace.tsx's file header for why the split is
 * deliberate).
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { GravitreFloatingWorkspace } from "@/components/gravitre/ai-floating-workspace"

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
  document.body.querySelectorAll("[data-gravitre-float-workspace]").forEach((el) => el.remove())
})

describe("GravitreFloatingWorkspace", () => {
  it("portals its content to document.body (not the local container), rendering the given children", () => {
    const onClose = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(
        createElement(
          GravitreFloatingWorkspace,
          { presence: "ready", onClose },
          createElement("div", { "data-testid": "float-body" }, "hello from float"),
        ),
      )
    })

    // Not rendered inside the local container — it's a portal.
    expect(container.querySelector("[data-testid='float-body']")).toBeNull()
    const portaled = document.body.querySelector("[data-gravitre-float-workspace]")
    expect(portaled).not.toBeNull()
    expect(portaled?.querySelector("[data-testid='float-body']")?.textContent).toBe("hello from float")
  })

  it("shows the given presence label in the header", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreFloatingWorkspace, { presence: "needs_approval", onClose: vi.fn() }, "x"))
    })
    const portaled = document.body.querySelector("[data-gravitre-float-workspace]")
    expect(portaled?.textContent).toContain("Needs approval")
  })

  it("calls onClose when the minimize-to-helper button is clicked", () => {
    const onClose = vi.fn()
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreFloatingWorkspace, { presence: "ready", onClose }, "x"))
    })
    const button = document.body.querySelector(
      "[data-gravitre-float-workspace] button[aria-label='Minimize to helper']",
    ) as HTMLButtonElement
    expect(button).toBeTruthy()
    act(() => {
      button.click()
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("marks the drag handle region, not the whole window, as the drag start zone", () => {
    root = createRoot(container)
    act(() => {
      root!.render(createElement(GravitreFloatingWorkspace, { presence: "ready", onClose: vi.fn() }, "x"))
    })
    const dragHandle = document.body.querySelector("[data-gravitre-float-workspace] [data-window-drag-handle]")
    expect(dragHandle).not.toBeNull()
  })
})
