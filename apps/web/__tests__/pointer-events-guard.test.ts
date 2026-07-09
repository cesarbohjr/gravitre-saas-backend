/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from "vitest"
import { clearStalePointerLocks } from "@/components/gravitre/pointer-events-guard"

describe("clearStalePointerLocks", () => {
  afterEach(() => {
    document.body.removeAttribute("data-scroll-locked")
    document.body.style.pointerEvents = ""
    document.body.style.overflow = ""
    document.body.style.paddingRight = ""
    document.documentElement.style.pointerEvents = ""
    document.body.innerHTML = ""
  })

  it("clears orphaned scroll-lock attributes when no dialog is open", () => {
    document.body.setAttribute("data-scroll-locked", "1")
    document.body.style.pointerEvents = "none"
    document.body.style.overflow = "hidden"

    const cleared = clearStalePointerLocks()

    expect(cleared).toBe(true)
    expect(document.body.hasAttribute("data-scroll-locked")).toBe(false)
    expect(document.body.style.pointerEvents).toBe("")
  })

  it("does not clear locks while a dialog overlay is open", () => {
    const overlay = document.createElement("div")
    overlay.setAttribute("data-slot", "dialog-overlay")
    overlay.setAttribute("data-state", "open")
    document.body.appendChild(overlay)
    document.body.setAttribute("data-scroll-locked", "1")
    document.body.style.pointerEvents = "none"

    const cleared = clearStalePointerLocks()

    expect(cleared).toBe(false)
    expect(document.body.hasAttribute("data-scroll-locked")).toBe(true)
    expect(document.body.style.pointerEvents).toBe("none")
  })
})
