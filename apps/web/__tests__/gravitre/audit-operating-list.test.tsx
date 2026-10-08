// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import AuditPage from "@/app/(app)/audit/page"
import type { AuditListResponse, AuditSummary } from "@/types/api"

const mocks = vi.hoisted(() => ({
  list: { data: undefined as (AuditListResponse & { fetchedAt: number }) | undefined, error: undefined as Error | undefined, isLoading: false, isValidating: false },
  summary: { data: undefined as AuditSummary | undefined, error: undefined as Error | undefined, isLoading: false },
  listKey: [] as unknown[], mutate: vi.fn(), refreshSummary: vi.fn(), export: vi.fn(), success: vi.fn(), error: vi.fn(),
}))
vi.mock("swr", () => ({ default: (key: unknown[]) => {
  if (key[0] === "audit/list") { mocks.listKey = key; return { ...mocks.list, mutate: mocks.mutate } }
  return { ...mocks.summary, mutate: mocks.refreshSummary }
} }))
vi.mock("@/lib/api", () => ({ auditApi: { export: mocks.export } }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "audit-user" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: false }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("next/navigation", () => ({ usePathname: () => "/audit" }))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const render = () => act(() => root.render(<AuditPage />))
const button = (text: string) => [...container.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === text)!
beforeEach(() => {
  vi.clearAllMocks()
  mocks.list = { data: { logs: [{ id: "event-1", action: "approve", entity_type: "approval", entity_id: "approval-1", entity_name: "Renewal", user_name: "Operator", created_at: "2026-10-01T14:00:00Z", details: { outcome: "approved", description: "Renewal approved" } }], total: 81, hasMore: true, fetchedAt: Date.now() - 120_000 }, error: undefined, isLoading: false, isValidating: false }
  mocks.summary = { data: { byAction: { approve: 81 }, byUser: [], byEntityType: { approval: 81 } }, error: undefined, isLoading: false }
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
it("does not turn failed list or summary into empty events and zero users", () => {
  mocks.list.data = undefined; mocks.list.error = new Error("List failed")
  mocks.summary.data = undefined; mocks.summary.error = new Error("Summary failed"); render()
  expect(container.textContent).not.toContain("No audit events yet")
  expect(container.querySelector('[aria-label="Audit summary"]')?.textContent).toContain("Active usersNot reported")
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(2)
  act(() => button("Retry").click()); act(() => button("Retry summary").click())
  expect(mocks.mutate).toHaveBeenCalledOnce(); expect(mocks.refreshSummary).toHaveBeenCalledOnce()
})
it("retains independent summary zeros and avoids false empty while the list loads", () => {
  mocks.list.data = undefined; mocks.list.isLoading = true; render()
  expect(container.querySelector('[aria-label="Loading audit events"]')).not.toBeNull()
  expect(container.textContent).not.toContain("No audit events yet")
  expect(container.querySelector('[aria-label="Audit summary"]')?.textContent).toContain("Active users0")
})
it("keeps pagination after page search matches no events", () => {
  render()
  const input = container.querySelector<HTMLInputElement>('input[aria-label="Search loaded audit events"]')!
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "no-such-event")
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
  expect(container.textContent).toContain("0 matching search")
  expect(button("Next").disabled).toBe(false)
  act(() => button("Next").click())
  expect(mocks.listKey.at(-1)).toBe(50)
  expect(button("Previous").disabled).toBe(false)
})
it("keeps the previous page available when the next request fails", () => {
  render(); act(() => button("Next").click())
  mocks.list.data = undefined; mocks.list.error = new Error("Page unavailable"); render()
  expect(container.textContent).toContain("Page 2 · Results unavailable")
  expect(button("Previous").disabled).toBe(false)
  act(() => button("Previous").click()); expect(mocks.listKey.at(-1)).toBe(0)
})
it("uses successful fetch time across rerenders and refreshes both resources", () => {
  render(); expect(container.textContent).toContain("2m ago")
  act(() => button("Next").click()); expect(container.textContent).toContain("2m ago")
  act(() => container.querySelector<HTMLButtonElement>('[aria-label="Refresh audit events"]')!.click())
  expect(mocks.mutate).toHaveBeenCalledOnce(); expect(mocks.refreshSummary).toHaveBeenCalledOnce()
})
it("retains readable event details behind an accessible disclosure", () => {
  render()
  const toggle = button("Show technical details")
  expect(toggle.getAttribute("aria-expanded")).toBe("false")
  act(() => toggle.click())
  expect(toggle.getAttribute("aria-expanded")).toBe("true")
  expect(document.getElementById(toggle.getAttribute("aria-controls")!)?.textContent).toContain('"outcome": "approved"')
})
it("preserves export failures without claiming a successful download", async () => {
  mocks.export.mockResolvedValue({ ok: false, status: 500 }); render()
  await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Export audit CSV"]')!.click())
  expect(mocks.export).toHaveBeenCalledWith("csv", expect.any(String))
  expect(mocks.error).toHaveBeenCalledWith("Failed to export audit logs")
  expect(mocks.success).not.toHaveBeenCalled()
})
