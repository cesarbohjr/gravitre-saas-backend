// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, expect, it, vi } from "vitest"
import ApprovalsPage from "@/app/(app)/approvals/page"
import { SHOT_FIXTURES } from "@/lib/e2e-shot-fixtures"
const state = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  approve: vi.fn(async () => ({ status: "running" })),
  reject: vi.fn(async () => ({ status: "cancelled" })),
  mutate: vi.fn(async () => undefined),
}))
vi.mock("next/navigation", () => {
  const params = new URLSearchParams()
  return { useSearchParams: () => params, usePathname: () => "/approvals", useRouter: () => ({ push: state.push, replace: state.replace }) }
})
vi.mock("swr", () => ({
  default: (key: string | null) => ({
    data: key === "/api/approvals" ? SHOT_FIXTURES["/api/approvals"] : { approvals: [] },
    mutate: state.mutate,
    isValidating: false,
  }),
}))
vi.mock("@/lib/api", () => ({ approvalsApi: { approve: state.approve, reject: state.reject } }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "fixture-owner" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: true, loading: false }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({ usePublishGravitreAISelection: vi.fn() }))
vi.mock("@/components/intelligence/ask-gravitre-summon-button", () => ({ AskGravitreSummonButton: () => null }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  state.approve.mockClear()
  state.reject.mockClear()
  state.push.mockClear()
})

function inspectTitle(host: HTMLElement) {
  return host.querySelector('[data-review-surface="approvals-inspect"] h3')?.textContent
}

function press(key: string) {
  window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }))
}

it("selects the oldest waiting request, switches locally on click and with J / K", async () => {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host)
  try {
    await act(async () => root.render(<ApprovalsPage />))
    const origin = window.location.href
    const cards = [...host.querySelectorAll<HTMLButtonElement>('[data-review-surface="approvals-queue"] .dq-item')]
    expect(cards.length).toBe(3)
    expect(inspectTitle(host)).toBe("Grant Zendesk write scope to the support workflow")
    await act(async () => cards[2].click())
    expect(inspectTitle(host)).toBe("Create HubSpot contact for Priya Raman")
    await act(async () => press("k"))
    expect(inspectTitle(host)).toBe("Update Salesforce opportunity stage to Negotiation")
    await act(async () => press("j"))
    expect(inspectTitle(host)).toBe("Create HubSpot contact for Priya Raman")
    expect(state.push).not.toHaveBeenCalled(); expect(state.replace).not.toHaveBeenCalled()
    expect(window.location.href).toBe(origin)
    // Stat tabs carry live counts from the queue.
    const waitingTab = host.querySelector('[data-tab="pending"]')
    expect(waitingTab?.textContent).toContain("3")
  } finally { act(() => root.unmount()); host.remove() }
})

it("A approves the selected request and R asks for a reason before rejecting", async () => {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host)
  try {
    await act(async () => root.render(<ApprovalsPage />))
    await act(async () => press("a"))
    expect(state.approve).toHaveBeenCalledWith("apr_01hq9a2f7t")

    await act(async () => press("r"))
    const reason = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Reason for rejecting"]')
    expect(reason).not.toBeNull()
    const confirm = [...document.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === "Reject" && b.closest('[role="alertdialog"]'))!
    expect(confirm.disabled).toBe(true)
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!
      setter.call(reason, "Use the Q3 segment instead")
      reason!.dispatchEvent(new Event("input", { bubbles: true }))
    })
    await act(async () => confirm.click())
    expect(state.reject).toHaveBeenCalledWith(expect.any(String), { comment: "Use the Q3 segment instead" })
  } finally { act(() => root.unmount()); host.remove() }
})
