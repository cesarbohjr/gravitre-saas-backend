// @vitest-environment jsdom
import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import LiteResultsPage from "@/app/(app)/lite/results/page"
import LiteTasksPage from "@/app/(app)/lite/tasks/page"
import LiteDeliverablesPage from "@/app/(app)/lite/deliverables/page"

const state = vi.hoisted(() => ({ data: undefined as unknown, error: undefined as unknown, mutate: vi.fn(), cancel: vi.fn() }))
vi.mock("swr", () => ({ default: () => ({ data: state.data, error: state.error, isLoading: false, mutate: state.mutate }) }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "owner" }, loading: false }) }))
vi.mock("@/lib/api", () => ({ liteApi: { cancelTask: state.cancel } }))
vi.mock("@/components/gravitre/lite-page-shell", () => ({ LitePageShell: ({ children, actions }: { children: ReactNode; actions: ReactNode }) => <main>{actions}{children}</main> }))
vi.mock("@/components/gravitre/nodus-product", () => ({ GravitreMetric: ({ label, value }: { label: string; value: ReactNode }) => <div>{label}: {value}</div> }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  state.data = undefined; state.error = undefined; vi.clearAllMocks()
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove() })
it("keeps omitted measurements unreported and preserves actual zeros", () => {
  state.data = { summary: { tasks_completed: 0, success_rate: 0, by_workflow: [] } }
  act(() => root.render(<LiteResultsPage />))
  expect(container.textContent).toContain("Avg completion (hrs): Not reported")
  expect(container.textContent).toContain("0%")
  expect(container.textContent).toContain("Workflows used: 0")
})
it.each([[LiteTasksPage, "No tasks yet."], [LiteDeliverablesPage, "No deliverables yet."], [LiteResultsPage, "No workflow results in this range."]])("shows a retry instead of false empty state after a request failure", (Page, empty) => {
  state.error = new Error("Service unavailable")
  act(() => root.render(<Page />))
  expect(container.textContent).toContain("Service unavailable")
  expect(container.textContent).not.toContain(empty)
  act(() => [...container.querySelectorAll<HTMLButtonElement>("button")].find(b => /retry|try again/i.test(b.textContent ?? ""))!.click())
  expect(state.mutate).toHaveBeenCalledOnce()
})
it("renders an unknown task status without inventing progress", () => {
  state.data = { tasks: [{ id: "task", status: "unrecognized", workflow_name: "Review", created_at: "2026-10-04T00:00:00Z" }] }
  act(() => root.render(<LiteTasksPage />))
  expect(container.textContent).toContain("Not reported")
})
it("prevents duplicate cancellations while the real API is pending", async () => {
  let finish!: () => void
  state.cancel.mockImplementation(() => new Promise<void>(resolve => { finish = resolve }))
  state.data = { tasks: [{ id: "task", status: "pending", workflow_name: "Review", progress: null, created_at: "2026-10-04T00:00:00Z" }] }
  act(() => root.render(<LiteTasksPage />))
  expect(container.textContent).toContain("Progress not reported")
  const button = [...container.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Cancel")!
  act(() => button.click())
  expect(button.disabled).toBe(true)
  expect(button.textContent).toBe("Cancelling…")
  await act(async () => { finish() })
  expect(state.cancel).toHaveBeenCalledExactlyOnceWith("task")
  expect(button.disabled).toBe(false)
})
