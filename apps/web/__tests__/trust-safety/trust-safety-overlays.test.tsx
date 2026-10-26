// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const agents = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), message: vi.fn(), loading: vi.fn(), dismiss: vi.fn(),
}))
const agentsConfirm = vi.hoisted(() => vi.fn())
vi.mock("@/components/agents/overlays/toast", () => ({ toast: agents }))
vi.mock("@/components/agents/overlays/confirm", () => ({ confirmDialog: agentsConfirm }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import {
  toast,
  MAX_VISIBLE_TRUST_SAFETY_TOASTS,
  TRUST_SAFETY_TOAST_DURATION_MS,
} from "@/components/trust-safety/overlays/toast"
import { confirmTrustSafety } from "@/components/trust-safety/overlays/confirm"
import { TrustSafetyOverlaysProvider } from "@/components/trust-safety/overlays/trust-safety-overlays"

let root: Root
let host: HTMLDivElement

beforeEach(() => {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  Object.values(agents).forEach((fn) => fn.mockReset())
  agentsConfirm.mockReset()
})

afterEach(() => {
  act(() => root.unmount())
  host.remove()
  vi.useRealTimers()
})

describe("Trust & Safety toasts", () => {
  it("hand off to the Agents toast when the Trust & Safety page is not open", () => {
    toast.success("Saved")
    toast.approval("Needs a person", { description: "Review it" })
    expect(agents.success).toHaveBeenCalledWith("Saved")
    expect(agents.warning).toHaveBeenCalledWith("Needs a person", { description: "Review it" })
  })

  it("render in the Trust & Safety shell with the tab eyebrow, at most three, and hide after six seconds", () => {
    vi.useFakeTimers()
    act(() => root.render(<TrustSafetyOverlaysProvider eyebrow="Policies"><div /></TrustSafetyOverlaysProvider>))
    act(() => {
      toast.success("Policy updated", { description: "Applies to new requests.", cancel: { label: "Undo", onClick: () => {} } })
    })
    expect(agents.success).not.toHaveBeenCalled()
    const first = host.querySelector(".tso-toast")
    expect(first?.getAttribute("data-tone")).toBe("success")
    expect(first?.querySelector(".tso-eyebrow")?.textContent).toBe("Policies")
    expect(first?.textContent).toContain("Undo")

    act(() => {
      toast.error("One")
      toast.info("Two")
      toast.warning("Three")
    })
    expect(host.querySelectorAll(".tso-toast")).toHaveLength(MAX_VISIBLE_TRUST_SAFETY_TOASTS)

    act(() => {
      vi.advanceTimersByTime(TRUST_SAFETY_TOAST_DURATION_MS + 50)
    })
    expect(host.querySelectorAll(".tso-toast")).toHaveLength(0)
  })

  it("labels approval toasts as needing your approval and runs the action", () => {
    const approve = vi.fn()
    act(() => root.render(<TrustSafetyOverlaysProvider eyebrow="Approvals"><div /></TrustSafetyOverlaysProvider>))
    act(() => {
      toast.approval("Billing change needs your approval", { action: { label: "Approve", onClick: approve } })
    })
    const card = host.querySelector('.tso-toast[data-tone="approval"]')
    expect(card?.querySelector(".tso-eyebrow")?.textContent).toBe("Needs your approval")
    act(() => {
      ;[...(card?.querySelectorAll("button") ?? [])].find((b) => b.textContent === "Approve")?.click()
    })
    expect(approve).toHaveBeenCalled()
    expect(host.querySelectorAll(".tso-toast")).toHaveLength(0)
  })
})

describe("Trust & Safety confirm", () => {
  it("hands off to the Agents confirm off the page", async () => {
    agentsConfirm.mockResolvedValue(true)
    await expect(confirmTrustSafety({ title: "Delete Staging?" })).resolves.toBe(true)
    expect(agentsConfirm).toHaveBeenCalledWith({ title: "Delete Staging?", tone: "danger" })
  })

  it("opens in the Trust & Safety shell on the page and resolves with the choice", async () => {
    act(() => root.render(<TrustSafetyOverlaysProvider eyebrow="Environments"><div /></TrustSafetyOverlaysProvider>))
    let answer: Promise<boolean> | undefined
    act(() => {
      answer = confirmTrustSafety({ title: "Delete Staging?", description: "This can't be undone.", confirmLabel: "Delete Staging" })
    })
    const dialog = document.querySelector('.tso-confirm[role="alertdialog"]')
    expect(dialog?.getAttribute("data-tone")).toBe("danger")
    expect(dialog?.textContent).toContain("This can't be undone.")
    await act(async () => {
      ;[...(dialog?.querySelectorAll("button") ?? [])].find((b) => b.textContent === "Delete Staging")?.click()
    })
    await expect(answer).resolves.toBe(true)
    expect(agentsConfirm).not.toHaveBeenCalled()
  })
})
