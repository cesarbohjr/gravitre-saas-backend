// @vitest-environment jsdom
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState: { value: string } = { value: "/home" }

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
}))

import { MobileBottomNav } from "@/components/gravitre/mobile-bottom-nav"

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/home"
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

function render() {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(MobileBottomNav, null))
  })
}

describe("MobileBottomNav", () => {
  it("does not include a Chat destination to /ai", () => {
    render()
    const links = Array.from(container.querySelectorAll("a"))
    expect(links.some((a) => a.getAttribute("href") === "/ai")).toBe(false)
    expect(links.map((a) => a.textContent?.trim())).toEqual([
      "Home",
      "Agents",
      "Activity",
      "Approvals",
      "Marketplace",
    ])
  })

  it("still returns null on /builder routes", () => {
    pathnameState.value = "/builder/123"
    render()
    expect(container.innerHTML).toBe("")
  })
})
