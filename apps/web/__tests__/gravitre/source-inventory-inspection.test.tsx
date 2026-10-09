// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import SourcesPage from "@/app/(app)/sources/page"
import { normalizeSource } from "@/lib/source-inventory"

const mocks = vi.hoisted(() => ({ refresh: vi.fn(), sync: vi.fn(), remove: vi.fn(), error: undefined as Error | undefined }))
vi.mock("swr", () => ({ default: () => ({ data: { sources: [source] }, error: mocks.error, isLoading: false, isValidating: false, mutate: mocks.refresh }) }))
vi.mock("@/lib/api", () => ({ sourcesApi: { sync: mocks.sync, delete: mocks.remove } }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "fixture-user" } }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/add-data-source-modal", () => ({ AddDataSourceModal: () => null }))
vi.mock("next/navigation", () => ({ usePathname: () => "/sources", useRouter: () => ({ push: vi.fn() }) }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const source = { id: "source-real", name: "Warehouse with a long name", type: "postgres", status: "connected", tables: 5, recordCount: 1200, workflowsUsing: 3, operatorsUsing: 2, topTables: ["accounts", "invoices", "renewals", "events", "service_requests"] }
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks(); mocks.error = undefined
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
it("does not infer a healthy connection when the backend omits or changes status", () => {
  expect(normalizeSource({ id: "missing" }).status).toBe("unknown")
  expect(normalizeSource({ id: "new", status: "pending_auth" }).status).toBe("unknown")
  expect(normalizeSource({ id: "known", status: "syncing" }).status).toBe("syncing")
  expect(normalizeSource({ id: "missing" }).health).toBeNull()
})
it("does not turn omitted inventory counts into zeros", () => {
  const omitted = normalizeSource({ id: "missing" })
  expect(omitted.tables).toBeNull()
  expect(omitted.recordCount).toBeNull()
  expect(omitted.records).toBe("Not reported")
  expect(omitted.workflowsUsing).toBeNull()
  expect(omitted.operatorsUsing).toBeNull()
  const zero = normalizeSource({ id: "empty", tables: 0, recordCount: 0, workflowsUsing: 0, operatorsUsing: 0 })
  expect(zero.tables).toBe(0)
  expect(zero.recordCount).toBe(0)
  expect(zero.records).toBe("0")
})
it("opens source context on tablet and retains full schema and workflow handoff", () => {
  act(() => root.render(<SourcesPage />))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  act(() => container.querySelector('[data-testid="sources-compact-view"] button')!.dispatchEvent(new MouseEvent("click", { bubbles: true })))
  const dialog = document.querySelector('[role="dialog"]')!
  expect(dialog.textContent).toContain("service_requests")
  expect(dialog.textContent).toContain("Not reported")
  expect(dialog.querySelector('a[href="/sources/source-real"]')).not.toBeNull()
  const workflow = [...dialog.querySelectorAll("a")].find(a => a.textContent?.includes("Use in workflow"))!
  expect(workflow.getAttribute("href")).toContain("sourceId=source-real")
  expect(workflow.getAttribute("href")).toContain("sourceName=Warehouse+with+a+long+name")
})
it("keeps sync and delete bound to the selected source and confirms delete", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
  act(() => root.render(<SourcesPage />))
  act(() => container.querySelector('[data-testid="sources-compact-view"] button')!.dispatchEvent(new MouseEvent("click", { bubbles: true })))
  const button = (text: string) => [...document.querySelectorAll('[role="dialog"] button')].find(b => b.textContent === text)!
  await act(async () => button("Sync source").dispatchEvent(new MouseEvent("click", { bubbles: true })))
  expect(mocks.sync).toHaveBeenCalledWith("source-real")
  await act(async () => button("Delete source").dispatchEvent(new MouseEvent("click", { bubbles: true })))
  expect(confirm).toHaveBeenCalled(); expect(mocks.remove).not.toHaveBeenCalled()
  confirm.mockRestore()
})
it("keeps the desktop inspector beside the inventory instead of under the table", () => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 1440 })
  act(() => root.render(<SourcesPage />))
  act(() => [...container.querySelectorAll('[data-testid="sources-table-view"] button')].at(0)!.dispatchEvent(new MouseEvent("click", { bubbles: true })))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  const operations = container.querySelector('[aria-label="Source operations"]')!
  expect(operations.textContent).toContain("service_requests")
  expect(operations.querySelector('a[href="/sources/source-real"]')).not.toBeNull()
})
it("shows failed fetch with retry without fabricating empty inventory", () => {
  mocks.error = new Error("Inventory unavailable")
  act(() => root.render(<SourcesPage />))
  expect(container.textContent).toContain("Inventory unavailable")
  expect(container.textContent).not.toContain("No data sources yet")
  act(() => [...container.querySelectorAll("button")].find(b => b.textContent === "Retry")!.click())
  expect(mocks.refresh).toHaveBeenCalled()
})
