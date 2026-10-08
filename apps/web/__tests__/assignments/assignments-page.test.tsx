// @vitest-environment jsdom
import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { DemoAssignment } from "@/lib/demo-assignments"

const state = vi.hoisted(() => ({
  assignments: [] as unknown[],
  agents: [{ id: "agent-1", name: "Lead Enrichment Coordinator", role: "Sales", status: "active" }],
  create: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | null) => {
    if (key === "assignments-list") return { data: state.assignments, error: undefined, isLoading: false, mutate: vi.fn() }
    if (key === "assignment-agents") return { data: { agents: state.agents }, isLoading: false }
    if (key === "assignment-installs") return { data: { installs: [] }, isLoading: false }
    return { data: undefined, isLoading: false }
  },
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { id: "u" } }) }))
vi.mock("@/components/gravitre/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }))
vi.mock("@/hooks/use-work-page-shortcut", () => ({ useWorkPageShortcut: vi.fn() }))
vi.mock("@/lib/assignments", () => ({ createAssignment: state.create, avatarGradient: () => "" }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import AssignmentsPage from "@/app/(app)/assignments/page"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement

const base = (over: Partial<DemoAssignment>): DemoAssignment => ({
  id: "a",
  title: "Title",
  brief: "Brief",
  agent: { name: "Lead Enrichment Coordinator", role: "AI Agent", gradient: "", icon: (() => null) as never },
  status: "completed",
  progress: 100,
  steps: [],
  createdAt: "2026-08-01T10:00:00Z",
  createdAtIso: "2026-08-01T10:00:00Z",
  outputTypes: [],
  destination: "Review",
  ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  state.assignments = []
  window.localStorage.clear()
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

it("renders four lanes with live counts and per-lane empty states", () => {
  act(() => root.render(<AssignmentsPage />))
  const lanes = [...container.querySelectorAll("[data-assignment-phase]")].map((el) => el.getAttribute("data-assignment-phase"))
  expect(lanes).toEqual(["queued", "running", "waiting", "delivered"])
  expect(container.textContent).toContain("0 executing")
  expect(container.textContent).toContain("No agent working")
  expect(container.querySelector('img[data-illustration="moment-paused-agents"]')).not.toBeNull()
  expect(container.querySelector('a[href="/approvals"]')?.textContent).toBe("Decision queue")
  expect(container.querySelector('a[href="/marketplace/assets?type=workflow"]')?.textContent).toBe("Browse workflow templates")
})

it("puts a blocked delivered job in Delivered with its flag, failed actions and confidence", () => {
  state.assignments = [
    base({
      id: "blocked",
      title: "Add MSP companies",
      resultSummary: "No companies were added.",
      confidence: 35,
      actions: { total: 5, failed: 3, succeeded: 2 },
      flag: { label: "Blocked by plan limit", tone: "amber", needsLook: true },
    }),
    base({ id: "run", status: "running", title: "Enrich contacts", progress: Number.NaN }),
  ]
  act(() => root.render(<AssignmentsPage />))
  const delivered = container.querySelector('[data-assignment-phase="delivered"]')!
  expect(delivered.textContent).toContain("Blocked by plan limit")
  expect(delivered.textContent).toContain("3 of 5")
  expect(delivered.textContent).toContain("35%")
  expect(container.textContent).toContain("1 executing")
  expect(container.textContent).toContain("1 delivered, needs a look")
  expect(container.querySelector('[data-assignment-phase="running"]')?.textContent).toContain("Enrich contacts")
})

it("switches to the list view of the same data", () => {
  state.assignments = [base({ id: "x", title: "Weekly report" })]
  act(() => root.render(<AssignmentsPage />))
  act(() => (container.querySelector('button[aria-label="List view"]') as HTMLButtonElement).click())
  expect(container.querySelector("[data-assignments-list]")?.textContent).toContain("Weekly report")
  expect(container.querySelector("[data-assignments-track]")).toBeNull()
})

it("creates a real assignment from the inline composer with the picked agent", async () => {
  state.create.mockResolvedValue({ id: "job-9", assignment: base({ id: "job-9", status: "pending", title: "Enrich the 40 newest contacts" }) })
  act(() => root.render(<AssignmentsPage />))
  const input = container.querySelector<HTMLInputElement>("#gvAssign")!
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!
  act(() => {
    setter.call(input, "Enrich the 40 newest contacts")
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
  await act(async () => {
    input.form!.requestSubmit()
  })
  expect(state.create).toHaveBeenCalledWith(expect.objectContaining({ agentId: "agent-1", task: "Enrich the 40 newest contacts" }))
  expect(container.querySelector('[data-assignment-phase="queued"]')?.textContent).toContain("Enrich the 40 newest contacts")
})
