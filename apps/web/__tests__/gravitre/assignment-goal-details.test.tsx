// @vitest-environment jsdom
import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import AssignmentDetailPage from "@/app/assignments/[id]/page"
import GoalDetailPage from "@/app/goals/[id]/page"
import { ExecutionTimeline, PreviewPanel, reportedAssignmentConfidence } from "@/components/assignments/assignment-detail-surfaces"
import { toast } from "sonner"
import type { AgentJob } from "@/hooks/use-async-job"

const state = vi.hoisted(() => ({ query: "", data: undefined as unknown, error: undefined as unknown, mutate: vi.fn(), approve: vi.fn(), push: vi.fn() }))
vi.mock("swr", () => ({ default: () => ({ data: state.data, error: state.error, isLoading: false, mutate: state.mutate }) }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "goal" }), useSearchParams: () => new URLSearchParams(state.query) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }))
vi.mock("@/components/gravitre/agent-identity-avatar", () => ({ AgentIdentityAvatar: () => null }))
vi.mock("@/components/intelligence/execution-mode-badge", () => ({ ExecutionModeBadge: () => null }))
vi.mock("@/components/gravitre/nodus-product", () => ({
  GravitrePageHeader: ({ title, actions, children }: { title: ReactNode; actions: ReactNode; children: ReactNode }) => <header><h1>{title}</h1>{actions}{children}</header>,
  GravitreMetric: ({ label, value }: { label: string; value: ReactNode }) => <div>{label}: {value}</div>,
  GravitreSurface: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  GravitreEmpty: ({ title, action }: { title: string; action: ReactNode }) => <div>{title}{action}</div>,
}))
vi.mock("@/lib/demo-assignments", () => ({ fetchAssignmentJob: vi.fn(), approveAssignment: state.approve, rejectAssignment: vi.fn(), pushAssignmentDeliverable: state.push, updateAssignmentDeliverable: vi.fn() }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const params = Object.assign(Promise.resolve({ id: "assignment" }), { status: "fulfilled", value: { id: "assignment" } })
const job: AgentJob = { jobId: "assignment", kind: "operator_task", status: "completed", result: { answer: "Returned report", agent_name: "Research agent", confidence: 0 }, error: null, sessionId: null, attempts: 1, createdAt: "2026-10-04T00:00:00Z", finishedAt: "2026-10-04T00:01:00Z" }
beforeEach(() => {
  vi.clearAllMocks(); state.data = undefined; state.error = undefined; state.query = ""
  state.mutate.mockImplementation(async updated => { if (updated) state.data = updated; return state.data })
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
const click = (scope: ParentNode, text: string) => act(() => [...scope.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.trim() === text)!.click())
it("discloses a selected deliverable in a compact sheet with separate selection and review controls", () => {
  state.data = job; act(() => root.render(<AssignmentDetailPage params={params} />))
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  const select = container.querySelector<HTMLButtonElement>('button[aria-pressed]')!
  expect(select.querySelector("button")).toBeNull()
  act(() => select.click())
  expect(document.querySelector('[data-slot="sheet-content"]')?.textContent).toContain("Returned report")
  expect(container.textContent).toContain("Agent-reported confidence: 0%")
})
it("does not mark approval locally while the persisted decision is pending", async () => {
  let finish!: (updated: AgentJob) => void
  state.approve.mockImplementation(() => new Promise<AgentJob>(resolve => { finish = resolve }))
  state.data = job; act(() => root.render(<AssignmentDetailPage params={params} />))
  click(container, "Review assignment")
  const dialog = document.querySelector('[role="dialog"]')!
  click(dialog, "Approve →")
  expect(container.textContent).not.toContain("Assignment approved")
  expect([...dialog.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.includes("Approve"))?.disabled).toBe(true)
  await act(async () => { finish({ ...job, result: { ...job.result as object, approval_status: "approved" } }) })
  expect(state.approve).toHaveBeenCalledExactlyOnceWith("assignment")
  expect(container.textContent).toContain("Assignment approved")
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Done")
})
it("keeps approval unset when the decision API fails", async () => {
  state.approve.mockRejectedValue(new Error("Permission denied")); state.data = job
  act(() => root.render(<AssignmentDetailPage params={params} />)); click(container, "Review assignment")
  const dialog = document.querySelector('[role="dialog"]')!
  await act(async () => [...dialog.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.trim() === "Approve →")!.click())
  expect(container.textContent).not.toContain("Assignment approved")
  expect(state.mutate).not.toHaveBeenCalled()
  expect(dialog.textContent).toContain("Approve →")
  expect(dialog.querySelector('[role="alert"]')?.textContent).toContain("Permission denied")
})
it("retains cached assignment output when refresh fails", () => {
  state.data = job; state.error = new Error("Network unavailable")
  act(() => root.render(<AssignmentDetailPage params={params} />))
  expect(container.textContent).toContain("Could not refresh assignment")
  expect(container.textContent).toContain("Returned report")
})
it("keeps returned evidence visible after task failure and disables unsupported action edits", () => {
  act(() => root.render(<PreviewPanel deliverable={{ id: "action-1", title: "Recommendation", type: "workflow", status: "ready", confidence: null, preview: "Retained output", sourceRefs: ["Document"] }} isApproved={false} canReview={false} canEdit={false} onApprove={vi.fn()} onEdit={vi.fn()} onPush={vi.fn()} jobError="Delivery failed" />))
  expect(container.textContent).toContain("Retained output")
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("Delivery failed")
  expect([...container.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Edit")?.disabled).toBe(true)
})
it("stops execution motion at rest and exposes textual failed/pending states", () => {
  act(() => root.render(<ExecutionTimeline steps={[{ id: "1", name: "Fetch", status: "completed" }, { id: "2", name: "Deliver", status: "error" }, { id: "3", name: "Review", status: "pending" }]} currentProgress={100} />))
  expect(container.querySelector('[class*="animate-spin"]')).toBeNull()
  expect(container.textContent).toContain("Failed")
  expect(container.textContent).toContain("Pending")
  expect(container.textContent).toContain("Reported progress")
})
it("distinguishes missing confidence, actual zero and invalid measurements", () => {
  expect(reportedAssignmentConfidence(undefined)).toBeNull()
  expect(reportedAssignmentConfidence(0)).toBe(0)
  expect(reportedAssignmentConfidence(0.82)).toBe(82)
  expect(reportedAssignmentConfidence(NaN)).toBeNull()
  expect(reportedAssignmentConfidence(101)).toBeNull()
})
it("does not invent goal progress or milestones when omitted", () => {
  state.data = { goal: { id: "goal", objective: "Retain customers" } }
  act(() => root.render(<GoalDetailPage />))
  expect(container.textContent).toContain("Not reported")
  expect(container.textContent).toContain("Milestones not reported")
  expect(container.querySelector('[role="progressbar"]')).toBeNull()
})
it("preserves zero progress and goal evidence during a failed refresh", () => {
  state.data = { goal: { id: "goal", objective: "Retain customers" }, completionPercentage: 0, milestoneStatus: [{ id: "milestone", title: "Contact customers", status: "in_progress" }] }
  state.error = new Error("Network unavailable")
  act(() => root.render(<GoalDetailPage />))
  expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("0")
  expect(container.textContent).toContain("Could not refresh goal")
  expect(container.textContent).toContain("Contact customers")
  expect(container.textContent).toContain("in progress")
})

it("can dismiss a review opened by the approval query without recording a decision", () => {
  state.data = job; state.query = "approval=1"
  act(() => root.render(<AssignmentDetailPage params={params} />))
  const dialog = document.querySelector('[role="dialog"]')!
  click(dialog, "Close")
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(state.approve).not.toHaveBeenCalled()
})
it("does not report a successful push when the destination returns ok:false", async () => {
  window.innerWidth = 1440
  state.data = { ...job, result: { ...job.result as object, approval_status: "approved" } }
  state.push.mockResolvedValue({ ok: false })
  act(() => root.render(<AssignmentDetailPage params={params} />))
  await act(async () => [...container.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.trim() === "Push to destination")!.click())
  expect(state.push).toHaveBeenCalledExactlyOnceWith("assignment")
  expect(toast.error).toHaveBeenCalledWith("Push failed", { description: "The destination did not confirm delivery" })
  expect(toast.success).not.toHaveBeenCalled()
})

it("does not invent execution phases or a percentage when the handoff omits its trace and progress", () => {
  state.data = job
  act(() => root.render(<AssignmentDetailPage params={params} />))
  expect(container.textContent).toContain("Reported progress: Not reported")
  expect(container.textContent).toContain("Step-level trace not reported")
  expect(container.textContent).not.toContain("Gathering Context")
  expect(container.querySelector('[role="progressbar"]')).toBeNull()
})
