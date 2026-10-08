// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { DemoAssignment } from "@/lib/demo-assignments"
import type { GoalRecord } from "@/lib/goals-list"
import {
  findRelatedAssignment,
  goalMeasure,
  goalSetupChecklist,
  goalStrengthChecks,
  relatedWorkSummary,
} from "@/lib/goal-insights"

const state = vi.hoisted(() => ({
  fetch: vi.fn(),
  mutate: vi.fn(),
  entries: {} as Record<string, { data?: unknown; error?: Error; isLoading?: boolean }>,
}))
vi.mock("swr", () => ({
  default: (key: unknown) => ({
    ...(key ? state.entries[typeof key === "string" ? key : JSON.stringify(key)] : {}),
    mutate: state.mutate,
  }),
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.fetch, fetcher: vi.fn(), ApiError: Error }))
vi.mock("@/lib/api", () => ({
  connectorsApi: { list: vi.fn() },
  agentsApi: { list: vi.fn() },
  workflowsApi: { fromGoal: vi.fn() },
  objectivesApi: { progress: vi.fn() },
}))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/goals",
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { id: "u1", user_metadata: { full_name: "Ada Lovelace" } } }),
}))
vi.mock("@/components/gravitre/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/components/ui/dropdown-menu", () => {
  const Box = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  return {
    DropdownMenu: Box,
    DropdownMenuTrigger: Box,
    DropdownMenuContent: Box,
    DropdownMenuSeparator: () => null,
    DropdownMenuItem: ({ children, onSelect }: { children: React.ReactNode; onSelect?: () => void }) => (
      <button data-menu-item onClick={() => onSelect?.()}>
        {children}
      </button>
    ),
  }
})
vi.mock("@/components/ui/dialog", () => {
  const Box = ({ children }: { children: React.ReactNode }) => <div>{children}</div>
  return {
    Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
      open ? <div data-dialog>{children}</div> : null,
    DialogContent: Box,
    DialogTitle: Box,
    DialogDescription: Box,
  }
})

import GoalsPage from "@/app/(app)/goals/page"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const draft: GoalRecord = {
  id: "g1",
  objective: "Get 100 MSP leads into HubSpot",
  department: "Sales",
  priority: "medium",
  frequency: "once",
  status: "draft",
  successMetrics: { metric: "MSP leads", start: 0, target: 100, owner: { id: "u1", name: "Ada Lovelace" } },
  createdAt: "2026-10-08T10:00:00Z",
}
const active: GoalRecord = {
  id: "g2",
  objective: "Reduce overdue invoices",
  department: "Finance",
  priority: "high",
  frequency: "weekly",
  status: "active",
  successMetrics: { dueDate: "2026-12-31" },
  createdAt: "2026-10-01T10:00:00Z",
}
function assignment(over: Partial<DemoAssignment>): DemoAssignment {
  return {
    id: "job-1",
    title: "Add MSP companies to the MSP prospect list",
    brief: "Find MSP leads and add them",
    agent: { name: "Lead Enrichment Coordinator", role: "AI Agent", gradient: "", icon: (() => null) as never },
    status: "failed",
    progress: Number.NaN,
    steps: [],
    createdAt: "2026-08-01T10:00:00Z",
    createdAtIso: "2026-08-01T10:00:00Z",
    outputTypes: [],
    destination: "Review",
    blocker: "Apollo search needs a plan with API access",
    ...over,
  }
}

describe("goal insights", () => {
  it("derives the setup checklist from real fields", () => {
    expect(goalSetupChecklist(draft).map((i) => i.done)).toEqual([true, true, false, false])
    expect(goalSetupChecklist(active).map((i) => i.done)).toEqual([true, true, true, true])
  })
  it("shows a draft's starting value but never invents progress for active goals", () => {
    const d = goalMeasure(draft)
    expect(d.current).toBe(0)
    expect(d.target).toBe(100)
    expect(d.percent).toBe(0)
    expect(d.stateLabel).toBe("Not started")
    expect(d.dueLabel).toBe("Due date not set")
    const a = goalMeasure(active)
    expect(a.current).toBeNull()
    expect(a.percent).toBeNull()
    expect(a.stateLabel).toBe("Progress not reported")
    expect(goalMeasure({ ...active, successMetrics: { start: 10, target: 30 } }, 20).percent).toBe(50)
  })
  it("matches related assignments only on shared key terms", () => {
    expect(findRelatedAssignment(draft, [assignment({})])?.id).toBe("job-1")
    expect(findRelatedAssignment(draft, [assignment({ title: "Weekly finance summary", brief: "Summarise cash" })])).toBeNull()
    expect(relatedWorkSummary(assignment({}))).toContain("It stopped: Apollo search needs a plan")
  })
  it("computes the strong goal checks from text and measure fields", () => {
    expect(goalStrengthChecks({ objective: "Get leads" }).map((c) => c.ok)).toEqual([false, false, false])
    expect(goalStrengthChecks({ objective: "Get 100 MSP leads by Dec 31" }).map((c) => c.ok)).toEqual([true, true, true])
    expect(goalStrengthChecks({ objective: "Get more MSP leads", target: "100", dueDate: "2026-12-31" }).every((c) => c.ok)).toBe(true)
  })
})

let root: Root
let host: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.entries = {}
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})
const render = (el: React.ReactNode) => act(() => root.render(el))
const buttons = () => [...host.querySelectorAll("button")]
const byText = (label: string) => {
  const found = buttons().find((b) => b.textContent?.trim() === label)
  if (!found) throw new Error(`Missing button: ${label}`)
  return found
}
const click = async (label: string) => {
  await act(async () => byText(label).click())
}
function type(selector: string, value: string) {
  const input = host.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement
  act(() => {
    Object.getOwnPropertyDescriptor(
      input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
}
const response = (body: unknown, ok = true) => ({ ok, json: async () => body })

describe("Goals page", () => {
  it("shows live status counts, filters by tab and shows related work with a link", async () => {
    state.entries["goals-list"] = { data: [draft, active] }
    state.entries["assignments-list"] = { data: [assignment({})] }
    render(<GoalsPage />)
    const tabs = host.querySelectorAll('nav[aria-label="Goal status"] button')
    expect([...tabs].map((t) => t.textContent)).toEqual(["1In motion", "1Draft", "0Paused", "0Completed", "0Cancelled"])
    // In motion is the default tab when something is active.
    expect(host.textContent).toContain("Reduce overdue invoices")
    expect(host.textContent).not.toContain("Get 100 MSP leads into HubSpot")
    expect(host.textContent).toContain("Due Dec 31, 2026")
    await act(async () => (tabs[1] as HTMLButtonElement).click())
    expect(host.textContent).toContain("Get 100 MSP leads into HubSpot")
    expect(host.textContent).toContain("Owned by Ada · Runs once")
    expect(host.textContent).toContain("2 of 4")
    expect(host.textContent).toContain("Gravitre found related work")
    expect(host.querySelector('a[href="/assignments/job-1"]')).not.toBeNull()
    expect(host.textContent).not.toContain("Link it to this goal")
    expect(host.querySelector('a[href="/marketplace/assets"]')?.textContent).toContain("See all in Explore")
  })
  it("hides the related work callout when nothing real matches", () => {
    state.entries["goals-list"] = { data: [draft] }
    state.entries["assignments-list"] = { data: [assignment({ title: "Close the books", brief: "Month end" })] }
    render(<GoalsPage />)
    expect(host.textContent).toContain("Get 100 MSP leads into HubSpot")
    expect(host.textContent).not.toContain("Gravitre found related work")
  })
  it("opens the New goal flow prefilled from a template", async () => {
    state.entries["goals-list"] = { data: [] }
    render(<GoalsPage />)
    expect(host.textContent).toContain("No goals yet")
    const card = buttons().find((b) => b.textContent?.includes("Reduce overdue invoices"))!
    await act(async () => card.click())
    expect((host.querySelector("#goal-objective") as HTMLTextAreaElement).value).toBe("Reduce overdue invoices")
    expect((host.querySelector("#goal-metric") as HTMLInputElement).value).toBe("Overdue invoices")
    expect(host.querySelector('img[src="/illustrations/dept-finance.svg"]')).not.toBeNull()
  })
  it("pauses an active goal through the goal API", async () => {
    state.entries["goals-list"] = { data: [active] }
    state.fetch.mockResolvedValue(response({ goal: { ...active, status: "paused" } }))
    render(<GoalsPage />)
    await click("Pause goal")
    expect(state.fetch).toHaveBeenCalledWith(
      "/api/goals/g2",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "paused" }) }),
    )
  })
})

describe("New goal flow", () => {
  it("saves measure fields and owner, then approves the plan and starts the goal", async () => {
    state.entries["goals/create/connectors"] = { data: { connectors: [] } }
    state.fetch
      .mockResolvedValueOnce(response({ goal: { id: "goal-new" } }))
      .mockResolvedValueOnce(
        response({
          planId: "plan-1",
          goalPlan: {
            id: "plan-1",
            proposedSteps: [{ id: "s1", title: "Find MSP companies" }],
            requiredConnectors: ["hubspot"],
            approvalGates: [{ stepId: "s1", phase: "pre-launch", required: true }],
          },
        }),
      )
      .mockResolvedValueOnce(response({ goal: { id: "goal-new", status: "active" } }))
    const saved = vi.fn()
    render(<GoalWorkflowWizard open onOpenChange={vi.fn()} onGoalSaved={saved} />)
    type("#goal-objective", "Get 100 MSP leads by Dec 31")
    type("#goal-metric", "MSP leads")
    type("#goal-target", "100")
    expect(host.textContent).toContain("Has a deadline.")
    await click("Sales")
    expect(host.querySelector('img[src="/illustrations/dept-sales.svg"]')).not.toBeNull()
    await click("Continue")
    await click("Generate plan")
    const body = JSON.parse(state.fetch.mock.calls[0][1].body)
    expect(body).toMatchObject({
      department: "Sales",
      status: "draft",
      successMetrics: { metric: "MSP leads", target: 100, owner: { name: "Ada Lovelace" } },
    })
    expect(host.textContent).toContain("Find MSP companies")
    expect(host.textContent).toContain("Approval gate")
    await click("Approve plan and start")
    expect(state.fetch.mock.calls[2][0]).toBe("/api/goals/goal-new")
    expect(JSON.parse(state.fetch.mock.calls[2][1].body)).toEqual({ status: "active" })
    expect(host.textContent).toContain("Plan approved. Your goal is in motion.")
    expect(host.querySelector('a[href="/approvals"]')).not.toBeNull()
  })
  it("continues setup on a saved goal with PATCH and keeps its contract", async () => {
    state.fetch.mockResolvedValueOnce(response({ goal: { id: "g1" } }))
    render(
      <GoalWorkflowWizard
        open
        onOpenChange={vi.fn()}
        initialGoal={{ ...draft, successMetrics: { ...draft.successMetrics, contract: { metricKey: "leads" } } }}
      />,
    )
    expect((host.querySelector("#goal-objective") as HTMLTextAreaElement).value).toBe(draft.objective)
    await click("Save draft")
    expect(state.fetch.mock.calls[0][0]).toBe("/api/goals/g1")
    const body = JSON.parse(state.fetch.mock.calls[0][1].body)
    expect(state.fetch.mock.calls[0][1].method).toBe("PATCH")
    expect(body.status).toBeUndefined()
    expect(body.successMetrics.contract).toEqual({ metricKey: "leads" })
  })
  it("refuses a non-numeric target without saving", async () => {
    render(<GoalWorkflowWizard open onOpenChange={vi.fn()} />)
    type("#goal-objective", "Grow signups")
    type("#goal-target", "lots")
    await click("Save draft")
    expect(state.fetch).not.toHaveBeenCalled()
    expect(host.textContent).toContain("Use a plain number")
  })
})
