// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const agents = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), message: vi.fn(), loading: vi.fn(), dismiss: vi.fn(),
}))
vi.mock("@/components/agents/overlays/toast", () => ({ toast: agents }))
vi.mock("next/navigation", () => ({ usePathname: () => "/intelligence/predictive" }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import {
  toast,
  MAX_VISIBLE_INTELLIGENCE_TOASTS,
  INTELLIGENCE_TOAST_DURATION_MS,
} from "@/components/intelligence/overlays/toast"
import { IntelligenceToaster, intelligenceEyebrowForPath } from "@/components/intelligence/overlays/intelligence-toaster"

let root: Root
let host: HTMLDivElement

beforeEach(() => {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  Object.values(agents).forEach((fn) => fn.mockReset())
})

afterEach(() => {
  act(() => root.unmount())
  host.remove()
  vi.useRealTimers()
})

describe("Intelligence toasts", () => {
  it("hand off to the Agents toast when the Intelligence toaster is not mounted", () => {
    toast.success("Saved")
    toast.approval("Needs a person", { description: "Review it" })
    toast.progress("Exporting", { progress: 0.4 })
    expect(agents.success).toHaveBeenCalledWith("Saved")
    expect(agents.warning).toHaveBeenCalledWith("Needs a person", { description: "Review it" })
    expect(agents.loading).toHaveBeenCalledWith("Exporting", {})
  })

  it("render in the Intelligence shell with the page eyebrow, at most three, and hide after six seconds", () => {
    vi.useFakeTimers()
    act(() => root.render(<IntelligenceToaster />))
    act(() => {
      toast.success("Forecast confirmed", { description: "Gravitre will weigh this next time." })
    })
    expect(agents.success).not.toHaveBeenCalled()
    const first = host.querySelector(".ig-toast")
    expect(first?.getAttribute("data-tone")).toBe("success")
    expect(first?.textContent).toContain("FORECASTS")
    expect(first?.textContent).toContain("Forecast confirmed")

    act(() => {
      toast.error("One")
      toast.info("Two")
      toast.warning("Three")
    })
    expect(host.querySelectorAll(".ig-toast")).toHaveLength(MAX_VISIBLE_INTELLIGENCE_TOASTS)

    act(() => {
      vi.advanceTimersByTime(INTELLIGENCE_TOAST_DURATION_MS + 50)
    })
    expect(host.querySelectorAll(".ig-toast")).toHaveLength(0)
  })

  it("keeps progress toasts until they finish and shows the real fraction", () => {
    vi.useFakeTimers()
    act(() => root.render(<IntelligenceToaster />))
    act(() => {
      toast.progress("Exporting report", { id: "export", progress: 0.25 })
    })
    act(() => {
      vi.advanceTimersByTime(INTELLIGENCE_TOAST_DURATION_MS * 2)
    })
    const bar = host.querySelector('[role="progressbar"]')
    expect(bar?.getAttribute("aria-valuenow")).toBe("25")
    act(() => {
      toast.success("Report exported", { id: "export" })
    })
    expect(host.querySelectorAll(".ig-toast")).toHaveLength(1)
    expect(host.querySelector(".ig-toast")?.getAttribute("data-tone")).toBe("success")
  })

  it("labels each Intelligence page", () => {
    expect(intelligenceEyebrowForPath("/intelligence/learning")).toBe("KNOWLEDGE")
    expect(intelligenceEyebrowForPath("/intelligence/performance")).toBe("IMPACT")
    expect(intelligenceEyebrowForPath("/models/abc")).toBe("MODELS")
    expect(intelligenceEyebrowForPath("/intelligence")).toBe("INTELLIGENCE")
  })
})
