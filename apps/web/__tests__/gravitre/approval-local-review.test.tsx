// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot } from "react-dom/client"
import { expect, it, vi } from "vitest"
import ApprovalsPage from "@/app/(app)/approvals/page"
import { SHOT_FIXTURES } from "@/lib/e2e-shot-fixtures"
const state = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }))
vi.mock("next/navigation", () => {
  const params = new URLSearchParams()
  return { useSearchParams: () => params, usePathname: () => "/e2e/shots/approvals", useRouter: () => ({ push: state.push, replace: state.replace }) }
})
vi.mock("swr", () => ({ default: (key: string) => ({ data: key === "/api/approvals" ? SHOT_FIXTURES["/api/approvals"] : { approvals: [], members: [] }, mutate: vi.fn() }) }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "fixture-owner" } }) }))
vi.mock("@/components/gravitre/user-account-avatar", () => ({ UserAccountAvatar: () => null }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({ usePublishGravitreAISelection: vi.fn() }))
vi.mock("@/components/intelligence/ask-gravitre-summon-button", () => ({ AskGravitreSummonButton: () => null }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
it("Decide opens local review and Back restores the queue without routing out", async () => {
  const host = document.createElement("div"); document.body.append(host); const root = createRoot(host)
  try {
    await act(async () => root.render(<ApprovalsPage />))
    const origin = window.location.href
    const decide = [...host.querySelectorAll("span")].find(node => node.textContent?.trim() === "Decide")!
    expect(decide).toBeTruthy()
    await act(async () => (decide.closest('[role="button"]') as HTMLElement).click())
    expect(host.querySelector('[data-review-surface="approvals-inspect"]')).not.toBeNull()
    const back = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent?.includes("Back"))!
    expect(back).toBeTruthy(); await act(async () => back.click())
    expect(state.push).not.toHaveBeenCalled(); expect(state.replace).not.toHaveBeenCalled()
    expect(window.location.href).toBe(origin)
  } finally { act(() => root.unmount()); host.remove() }
})
