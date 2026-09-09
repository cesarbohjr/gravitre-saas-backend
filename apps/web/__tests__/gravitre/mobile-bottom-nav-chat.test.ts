// @vitest-environment jsdom
/**
 * MobileBottomNav — Phase 4 (B7 open decision #3): "Chat" item behavior.
 *
 * Architecture doc's B7 flagged an open question — should the mobile
 * bottom-nav's "Chat" item still deep-link to the full `/ai` page, or should
 * it now open the Helper's floating/sheet workspace instead?
 *
 * This phase's disclosed decision (see the Phase 4 delivery report): leave
 * `MobileBottomNav` COMPLETELY UNTOUCHED, regardless of the
 * `NEXT_PUBLIC_AI_FLOAT_ENABLED` flag's value. `MobileBottomNav` itself is
 * not gated by the flag at all — repointing "Chat" to
 * `GravitreAIMobileSheet` is deferred in full to the real Phase 5 rollout
 * decision, not attempted even conditionally behind the flag in this phase.
 * This test proves that decision literally: "Chat" always renders as a
 * plain `<Link href="/ai">`, both with the flag off (the default) and with
 * it on — i.e. the flag has zero effect on this component's behavior.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState: { value: string } = { value: "/dashboard" }

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
}))

import { MobileBottomNav } from "@/components/gravitre/mobile-bottom-nav"

const ENV_KEY = "NEXT_PUBLIC_AI_FLOAT_ENABLED"
const originalValue = process.env[ENV_KEY]

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/dashboard"
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
  if (originalValue === undefined) delete process.env[ENV_KEY]
  else process.env[ENV_KEY] = originalValue
})

function render() {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(MobileBottomNav, null))
  })
}

describe("MobileBottomNav 'Chat' item — unchanged regardless of NEXT_PUBLIC_AI_FLOAT_ENABLED (B7)", () => {
  it("with the flag OFF (default): 'Chat' is a plain link to /ai, not a Gravitre AI workspace control", () => {
    delete process.env[ENV_KEY]
    render()
    const links = Array.from(container.querySelectorAll("a"))
    const chatLink = links.find((a) => a.textContent?.includes("Chat"))
    expect(chatLink).toBeTruthy()
    expect(chatLink?.getAttribute("href")).toBe("/ai")
    // No Gravitre AI workspace markers anywhere in this nav, flag off or on —
    // this component never renders float/sheet UI itself.
    expect(container.querySelector("[data-gravitre-ai-helper]")).toBeNull()
    expect(container.querySelector("[data-gravitre-mobile-sheet]")).toBeNull()
  })

  it("with the flag ON: 'Chat' is STILL a plain link to /ai — MobileBottomNav is not flag-gated at all", () => {
    process.env[ENV_KEY] = "true"
    render()
    const links = Array.from(container.querySelectorAll("a"))
    const chatLink = links.find((a) => a.textContent?.includes("Chat"))
    expect(chatLink).toBeTruthy()
    expect(chatLink?.getAttribute("href")).toBe("/ai")
  })

  it("renders all 5 expected destinations unchanged (Home, Chat, Agents, Activity, Approvals)", () => {
    render()
    const labels = Array.from(container.querySelectorAll("a")).map((a) => a.textContent)
    expect(labels).toEqual(["Home", "Chat", "Agents", "Activity", "Approvals"])
  })

  it("still returns null on /builder routes, flag on or off (pre-existing behavior, unmodified)", () => {
    pathnameState.value = "/builder/123"
    process.env[ENV_KEY] = "true"
    render()
    expect(container.innerHTML).toBe("")
  })
})
