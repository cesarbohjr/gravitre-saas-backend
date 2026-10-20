// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { AuditTrail as AuditPage_ } from "@/components/settings/audit-trail"
import type { AuditListPayload, AuditSummaryPayload } from "@/lib/settings-api/audit"
// Audit trail moved to Trust & Safety hub. Tests use the component directly (standalone mode).
const AuditPage = () => <AuditPage_ standalone />

const mocks = vi.hoisted(() => ({
  list: {
    data: undefined as (AuditListPayload & { fetchedAt: number }) | undefined,
    error: undefined as Error | undefined,
    isLoading: false,
    isValidating: false,
  },
  summary: { data: undefined as AuditSummaryPayload | undefined, error: undefined as Error | undefined, isLoading: false },
  listKey: [] as unknown[],
  mutate: vi.fn(),
  refreshSummary: vi.fn(),
  exportAudit: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))
vi.mock("swr", () => ({
  default: (key: unknown[] | null) => {
    if (key && key[0] === "settings/audit/list") {
      mocks.listKey = key
      return { ...mocks.list, mutate: mocks.mutate }
    }
    return { ...mocks.summary, isValidating: false, mutate: mocks.refreshSummary }
  },
}))
vi.mock("@/lib/settings-api/audit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/settings-api/audit")>()
  return { ...actual, exportAudit: mocks.exportAudit, listAudit: vi.fn(), auditSummary: vi.fn() }
})
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "audit-user" } }) }))
vi.mock("@/lib/use-org-admin", () => ({ useOrgAdmin: () => ({ isAdmin: true, showAdmin: true }) }))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}))
vi.mock("@/components/settings/settings-shell", () => ({
  SettingsShell: ({ children, actions }: { children: React.ReactNode; actions?: React.ReactNode }) => (
    <div className="gv-set">
      <div data-testid="actions">{actions}</div>
      {children}
    </div>
  ),
}))
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: mocks.error } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const RUN_ID = "00000000-0000-0000-0000-0000000000a1"
let root: Root
let container: HTMLDivElement
const render = () => act(() => root.render(<AuditPage />))
const buttons = () => [...container.querySelectorAll<HTMLButtonElement>("button")]
const button = (text: string) => buttons().find((b) => b.textContent?.trim() === text)!
const select = (label: string) => container.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`)!
const change = (el: HTMLSelectElement | HTMLInputElement, value: string) =>
  act(() => {
    const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value)
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
  })

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, "", "/audit")
  mocks.list = {
    data: {
      logs: [
        {
          id: "event-1",
          action: "tool.invoke.failed",
          category: "chat",
          outcome: "error",
          error_message: "HubSpot returned 401.",
          entity_type: "workflow_run",
          entity_id: RUN_ID,
          user_name: "Dana Admin",
          created_at: "2026-10-01T14:00:00Z",
          details: { action: "hubspot.contacts.create", run_id: RUN_ID, duration_ms: 412, environment: "production" },
        },
      ],
      total: 66,
      hasMore: true,
      actors: 2,
      errors: 5,
      truncated: false,
      fetchedAt: Date.now() - 120_000,
    },
    error: undefined,
    isLoading: false,
    isValidating: false,
  }
  mocks.summary = {
    data: { byAction: {}, byUser: [{ user_id: "u-1", user_name: "Dana Admin", count: 40 }], byEntityType: {} },
    error: undefined,
    isLoading: false,
  }
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

it("shows server totals in the tiles and drives the pager from the server total", () => {
  render()
  const intro = container.querySelector('[aria-label="Audit summary"]')!.textContent
  expect(intro).toContain("66Matching events")
  expect(intro).toContain("2Active users")
  expect(intro).toContain("5Errors")
  expect(container.textContent).toContain("Showing 1 to 1 of 66")
  expect(container.querySelector('[aria-label="Page 7"]')).not.toBeNull()
  act(() => container.querySelector<HTMLButtonElement>('[aria-label="Next page"]')!.click())
  expect(mocks.listKey.at(-1)).toBe(10)
  expect(container.textContent).toContain("Exports cover the whole date range, not just this page.")
})

it("does not turn a failed list into empty events or zero totals", () => {
  mocks.list.data = undefined
  mocks.list.error = new Error("List failed")
  render()
  expect(container.textContent).not.toContain("No events")
  expect(container.querySelector('[aria-label="Audit summary"]')!.textContent).toContain("UnavailableActive users")
  act(() => button("Try again").click())
  expect(mocks.mutate).toHaveBeenCalledOnce()
  expect(container.textContent).toContain("Update failed")
})

it("shows loading without a false empty state", () => {
  mocks.list.data = undefined
  mocks.list.isLoading = true
  render()
  expect(container.querySelector('[aria-label="Loading audit events"]')).not.toBeNull()
  expect(container.textContent).not.toContain("No events")
})

it("sends filters to the server and resets to page one", () => {
  render()
  act(() => container.querySelector<HTMLButtonElement>('[aria-label="Page 3"]')!.click())
  expect(mocks.listKey.at(-1)).toBe(20)
  change(select("Outcome"), "err")
  expect(mocks.listKey).toContain("err")
  expect(mocks.listKey.at(-1)).toBe(0)
  change(select("Action"), "sync")
  expect(mocks.listKey).toContain("sync")
  change(select("Person"), "u-1")
  expect(mocks.listKey).toContain("u-1")
})

it("expands an event to its real metadata, error line and confirmation link", () => {
  render()
  expect(container.textContent).toContain("Error: HubSpot returned 401.")
  const toggle = buttons().find((b) => b.getAttribute("aria-expanded") === "false")!
  act(() => toggle.click())
  expect(toggle.getAttribute("aria-expanded")).toBe("true")
  const details = document.getElementById(toggle.getAttribute("aria-controls")!)!
  expect(details.textContent).toContain("Environmentproduction")
  expect(details.textContent).toContain("Duration412 ms")
  expect(details.textContent).toContain("Tool actionhubspot.contacts.create")
  expect(details.querySelector(`a[href="/runs/${RUN_ID}"]`)).not.toBeNull()
})

it("switches to the table view", () => {
  render()
  act(() => button("Table").click())
  expect(button("Table").getAttribute("aria-pressed")).toBe("true")
  expect(container.querySelector('[aria-label="Audit events table"]')).not.toBeNull()
})

it("applies deep link query params from chat replies", () => {
  window.history.replaceState(null, "", "/audit?category=chat&outcome=err&range=30d&view=table")
  render()
  expect(mocks.listKey).toContain("chat")
  expect(mocks.listKey).toContain("err")
  expect(mocks.listKey).toContain("30d")
  expect(button("Table").getAttribute("aria-pressed")).toBe("true")
})

it("reports the real last fetch time and refreshes both resources", () => {
  render()
  expect(container.textContent).toContain("Updated 2 minutes ago")
  act(() => container.querySelector<HTMLButtonElement>('[aria-label="Refresh audit events"]')!.click())
  expect(mocks.mutate).toHaveBeenCalledOnce()
  expect(mocks.refreshSummary).toHaveBeenCalledOnce()
})

it("exports the whole range with the current filters and reports failures honestly", async () => {
  mocks.exportAudit.mockResolvedValue({ ok: false, status: 500 })
  render()
  change(select("Outcome"), "err")
  await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Export audit CSV"]')!.click())
  expect(mocks.exportAudit).toHaveBeenCalledWith("csv", expect.objectContaining({ outcome: "err", range: "7d" }), expect.any(String))
  expect(mocks.error).toHaveBeenCalledWith("Failed to export audit logs")
  expect(mocks.success).not.toHaveBeenCalled()
})

it("shows the empty state with a clear action when filters match nothing", () => {
  mocks.list.data = { ...mocks.list.data!, logs: [], total: 0, actors: 0, errors: 0 }
  render()
  change(select("Outcome"), "err")
  expect(container.textContent).toContain("No events match these filters.")
  act(() => button("Clear filters").click())
  expect(select("Outcome").value).toBe("all")
})
