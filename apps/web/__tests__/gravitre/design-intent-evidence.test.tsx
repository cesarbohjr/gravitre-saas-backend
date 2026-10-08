// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import SourceDetailPage from "@/app/(app)/sources/[id]/page"
import { formatReportedCount, reportedNumber, sourceSyncFeedback } from "@/lib/source-evidence"

const state = vi.hoisted(() => ({
  entries: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
  sync: vi.fn(), remove: vi.fn(), refresh: vi.fn(), selected: vi.fn(),
  success: vi.fn(), error: vi.fn(), message: vi.fn(), push: vi.fn(),
}))
vi.mock("swr", () => ({ default: (key: string) => ({ ...state.entries[key], mutate: state.refresh }) }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "owner" } }) }))
vi.mock("@/lib/api", () => ({ sourcesApi: { sync: state.sync, delete: state.remove, testExisting: vi.fn() } }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "source-a" }), useRouter: () => ({ push: state.push }), usePathname: () => "/sources/source-a" }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/source-query-panel", () => ({ SourceQueryPanel: () => null }))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({ usePublishGravitreAISelection: state.selected }))
vi.mock("@/components/intelligence/ask-gravitre-summon-button", () => ({ AskGravitreSummonButton: () => null }))
vi.mock("sonner", () => ({ toast: { success: state.success, error: state.error, message: state.message } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root
beforeEach(() => {
  vi.clearAllMocks()
  state.entries = { "/api/sources/source-a": { data: { source: { id: "source-a", name: "Grounding source" } } } }
  state.refresh.mockResolvedValue(undefined)
  host = document.createElement("div"); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove() })
async function render() { await act(async () => root.render(<SourceDetailPage />)) }
async function click(text: string) {
  const target = Array.from((document.querySelector('[role="dialog"]') ?? document).querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent?.trim() === text)
  expect(target, text).toBeTruthy()
  await act(async () => target!.click())
}
it("preserves real zeros and rejects absent/invalid measurements", () => {
  for (const value of [undefined, null, "0", NaN, Infinity, -1]) {
    expect(reportedNumber(value)).toBeNull()
    expect(formatReportedCount(value)).toBe("Not reported")
  }
  expect(formatReportedCount(0)).toBe("0")
})
it("distinguishes failed, in-progress, completed and unknown sync results", () => {
  expect(sourceSyncFeedback({ success: false, status: "connected", error: "Test refused" })).toEqual({ kind: "error", message: "Test refused" })
  expect(sourceSyncFeedback({ status: "queued" }).kind).toBe("pending")
  expect(sourceSyncFeedback({ success: true, status: "connected" }).kind).toBe("success")
  expect(sourceSyncFeedback({ status: "new_status" }).kind).toBe("unknown")
})
it("does not invent lifecycle, environment, counts or timestamps for a sparse source", async () => {
  await render()
  expect(host.textContent).toContain("Not reported")
  expect(host.textContent).toContain("Environment not reported")
  expect(host.textContent).not.toContain("connected")
  expect(host.textContent).not.toContain("Never")
  expect(host.textContent).not.toContain("Every 5 minutes")
  expect(state.selected).toHaveBeenCalledWith({ kind: "source", id: "source-a", label: "Grounding source" })
})
it("keeps cached schema and exposes independent retry after refresh failure", async () => {
  state.entries["/api/sources/source-a/schema"] = { data: { tables: [{ name: "accounts", columns: [] }] }, error: new Error("offline") }
  await render()
  expect(host.textContent).toContain("accounts")
  expect(host.textContent).toContain("Could not refresh schema")
  await click("Try again")
  expect(state.refresh).toHaveBeenCalled()
})
it("does not announce success when sync returns an error without throwing", async () => {
  state.sync.mockResolvedValue({ success: false, status: "error", error: "Connection refused" })
  await render(); await click("Sync Now")
  expect(state.error).toHaveBeenCalledWith("Connection refused")
  expect(state.success).not.toHaveBeenCalled()
})
it("prevents duplicate delete and keeps a failed confirmation open", async () => {
  let reject!: (error: Error) => void
  state.remove.mockImplementation(() => new Promise((_resolve, fail) => { reject = fail }))
  await render(); await click("Remove source")
  await click("Remove source"); await click("Removing…")
  expect(state.remove).toHaveBeenCalledTimes(1)
  await act(async () => reject(new Error("Removal refused")))
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Removal refused")
  expect(state.push).not.toHaveBeenCalled()
})

it("preserves source context when its refresh fails", async () => {
  state.entries["/api/sources/source-a"].error = new Error("offline")
  await render()
  expect(host.textContent).toContain("Grounding source")
  expect(host.textContent).toContain("Source refresh unavailable")
  await click("Try again")
  expect(state.refresh).toHaveBeenCalled()
})
