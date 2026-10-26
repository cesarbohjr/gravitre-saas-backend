// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const sonner = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), message: vi.fn(), dismiss: vi.fn() }))
vi.mock("sonner", () => ({ toast: sonner }))
vi.mock("next/navigation", () => ({ usePathname: () => "/sources" }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { toast, MAX_VISIBLE_TOASTS, TOAST_DURATION_MS } from "@/components/agents/overlays/toast"
import { AgentsToaster, eyebrowForPath } from "@/components/agents/overlays/agents-toaster"
import { confirmDialog } from "@/components/agents/overlays/confirm"
import { isAgentsSurfacePath } from "@/components/agents/overlays/surface-context"
import { ApprovalsArt, SourcesArt } from "@/components/agents/art/agents-art"

let root: Root
let host: HTMLDivElement

beforeEach(() => {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  Object.values(sonner).forEach((fn) => fn.mockReset())
})

afterEach(() => {
  act(() => root.unmount())
  host.remove()
  vi.useRealTimers()
})

describe("Agents toasts", () => {
  it("go to the existing toaster when the Agents toaster is not mounted", () => {
    toast.success("Saved")
    toast.error("Failed", { description: "Try again" })
    expect(sonner.success).toHaveBeenCalledWith("Saved")
    expect(sonner.error).toHaveBeenCalledWith("Failed", { description: "Try again" })
  })

  it("render in the Agents shell with the page eyebrow, at most three, and hide after six seconds", () => {
    vi.useFakeTimers()
    act(() => root.render(<AgentsToaster />))
    act(() => {
      toast.success("HubSpot connected", { description: "Indexing now." })
    })
    expect(sonner.success).not.toHaveBeenCalled()
    const first = host.querySelector(".ag-toast")
    expect(first?.getAttribute("data-tone")).toBe("success")
    expect(first?.textContent).toContain("SOURCES")
    expect(first?.textContent).toContain("HubSpot connected")
    expect(first?.textContent).toContain("Indexing now.")

    act(() => {
      toast.error("One")
      toast.info("Two")
      toast.warning("Three")
    })
    const cards = host.querySelectorAll(".ag-toast")
    expect(cards).toHaveLength(MAX_VISIBLE_TOASTS)
    expect(host.textContent).not.toContain("HubSpot connected")
    expect(host.querySelector('.ag-toast[data-tone="error"]')?.getAttribute("role")).toBe("alert")

    act(() => {
      vi.advanceTimersByTime(TOAST_DURATION_MS + 10)
    })
    expect(host.querySelectorAll(".ag-toast")).toHaveLength(0)
  })

  it("pause while hovered and run the action before closing", () => {
    vi.useFakeTimers()
    const onClick = vi.fn()
    act(() => root.render(<AgentsToaster />))
    act(() => {
      toast.warning("3 actions are waiting on you", { action: { label: "Open queue", onClick } })
    })
    const stack = host.querySelector(".ag-toasts") as HTMLElement
    act(() => {
      stack.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }))
    })
    act(() => {
      vi.advanceTimersByTime(TOAST_DURATION_MS * 2)
    })
    expect(host.querySelectorAll(".ag-toast")).toHaveLength(1)

    const button = Array.from(host.querySelectorAll("button")).find((b) => b.textContent === "Open queue")!
    act(() => button.click())
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(host.querySelectorAll(".ag-toast")).toHaveLength(0)
  })

  it("update a loading toast in place when its promise settles", async () => {
    act(() => root.render(<AgentsToaster />))
    let resolve: (value: string) => void = () => {}
    const pending = new Promise<string>((r) => (resolve = r))
    act(() => {
      toast.promise(pending, { loading: "Syncing", success: (v) => `Synced ${v}`, error: "Sync failed" })
    })
    expect(host.querySelector(".ag-toast")?.getAttribute("data-tone")).toBe("loading")
    await act(async () => {
      resolve("12 tables")
      await pending
    })
    const cards = host.querySelectorAll(".ag-toast")
    expect(cards).toHaveLength(1)
    expect(cards[0].getAttribute("data-tone")).toBe("success")
    expect(cards[0].textContent).toContain("Synced 12 tables")
  })
})

describe("Agents surface", () => {
  it("covers the signed-in app but not Lite", () => {
    expect(isAgentsSurfacePath("/activity")).toBe(true)
    expect(isAgentsSurfacePath("/settings")).toBe(true)
    expect(isAgentsSurfacePath("/lite")).toBe(false)
    expect(isAgentsSurfacePath("/lite/tasks")).toBe(false)
    expect(isAgentsSurfacePath("/literature")).toBe(true)
  })

  it("labels toasts by the page they came from", () => {
    expect(eyebrowForPath("/approvals")).toBe("APPROVALS")
    expect(eyebrowForPath("/trust-safety")).toBe("TRUST AND SAFETY")
    expect(eyebrowForPath("/")).toBe("HOME")
  })

  it("falls back to the browser confirm when no Agents confirm is mounted", async () => {
    const spy = vi.spyOn(window, "confirm").mockReturnValue(true)
    await expect(confirmDialog({ title: "Delete HubSpot?", description: "Agents lose read access." })).resolves.toBe(true)
    expect(spy).toHaveBeenCalledWith("Delete HubSpot?\n\nAgents lose read access.")
    spy.mockRestore()
  })
})

describe("Agents art", () => {
  it("draws one broken pipe per failing source, up to three", () => {
    act(() => root.render(<SourcesArt broken={2} />))
    expect(host.querySelector("svg")?.getAttribute("aria-label")).toBe(
      "Databases piped into a Gravitre hub with 2 broken connections",
    )
    expect(host.querySelectorAll('path[stroke-dasharray="7 7"]')).toHaveLength(2)
    act(() => root.render(<SourcesArt broken={5} />))
    expect(host.querySelectorAll('path[stroke-dasharray="7 7"]')).toHaveLength(3)
    act(() => root.render(<SourcesArt broken={0} />))
    expect(host.querySelectorAll('path[stroke-dasharray="7 7"]')).toHaveLength(0)
  })

  it("shows the waiting count on the queue only when something waits", () => {
    act(() => root.render(<ApprovalsArt waiting={0} />))
    expect(host.querySelector("svg")?.getAttribute("aria-label")).toContain("Decision queue is clear")
    expect(host.querySelector("text")).toBeNull()
    act(() => root.render(<ApprovalsArt waiting={3} />))
    expect(host.querySelector("text")?.textContent).toBe("3")
  })
})
