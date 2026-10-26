// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

/**
 * Gravitre 3.0 Plus surfaces: each hides itself while its backend flag is off
 * (the route answers 404), shows evidence and rules when on, and proposals
 * change only by an explicit accept or dismiss.
 */

const state = vi.hoisted(() => ({
  entries: {} as Record<string, { data?: unknown; error?: unknown; isLoading?: boolean }>,
  accept: vi.fn(),
  dismiss: vi.fn(),
  start: vi.fn(),
  refresh: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | string[] | null) => ({
    ...(key ? state.entries[Array.isArray(key) ? key[0] : key] : {}),
    mutate: state.refresh,
  }),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
import { toast } from "sonner"
vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))
vi.mock("@/lib/api", () => ({
  accountIntelligenceApi: { acceptProposal: state.accept, dismissProposal: state.dismiss, startPlayRun: state.start },
  isFeatureOff: (e: unknown) => typeof e === "object" && e !== null && (e as { status?: number }).status === 404,
}))

import { RecommendationFeedPanel } from "@/components/accounts/recommendation-feed-panel"
import { GoalLinkedProgress } from "@/components/goals/goal-linked-progress"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root
const off = { status: 404, message: "Not found" }

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

async function render(node: React.ReactNode) {
  await act(async () => root.render(node))
}

const GOVERNANCE = "/api/settings/source-governance"
const governance = (enabled: boolean) => ({
  data: { sourceDataGovernance: { customerContext: { enabled, connectors: [] }, retentionDays: {} } },
})
const settingsLink = () =>
  [...host.querySelectorAll("a")].find((a) => a.getAttribute("href") === "/settings?section=ai-models#customer-data")

describe("switched off", () => {
  it("goal progress still renders nothing", async () => {
    state.entries = { "goal-linked-progress": { error: off } }
    await render(<GoalLinkedProgress goalId="g1" />)
    expect(host.textContent).toBe("")
  })

  it("the recommendation feed says it is off instead of hiding", async () => {
    state.entries = { "recommendation-feed": { error: off }, [GOVERNANCE]: governance(false) }
    await render(<RecommendationFeedPanel />)
    expect(host.textContent).toContain("Needs attention isn't switched on for your workspace yet")
    expect(settingsLink()).toBeTruthy()
  })
})

describe("recommendation feed", () => {
  it("accepts a proposal only when asked", async () => {
    state.accept.mockResolvedValue({ workObject: { id: "w1", status: "planned" } })
    state.entries = {
      "recommendation-feed": {
        data: {
          generatedAt: "",
          sources: { proposals: "ok", business_signals: "error" },
          items: [
            {
              id: "proposal:w1",
              kind: "proposed_work",
              title: "Review Acme for Customer Rescue",
              why: "Sentiment at risk",
              evidence: ["Customer sentiment: at risk"],
              source: "account_health",
              score: 0.8,
              href: "/activity?tab=objects",
              actions: ["accept", "dismiss"],
              advisoryOnly: true,
              workObjectId: "w1",
            },
          ],
        },
      },
    }
    await render(<RecommendationFeedPanel />)
    expect(host.textContent).toContain("Nothing here runs by itself")
    expect(host.textContent).toContain("One source couldn't be read")
    expect(state.accept).not.toHaveBeenCalled()
    const accept = [...host.querySelectorAll("button")].find((b) => b.textContent === "Accept")!
    await act(async () => accept.click())
    expect(state.accept).toHaveBeenCalledWith("w1")
    expect(state.dismiss).not.toHaveBeenCalled()
    expect(state.refresh).toHaveBeenCalled()
  })

  it("offers the governed Play run after accepting, and starts it only on click", async () => {
    const run = {
      method: "POST",
      path: "/api/plays/customer-rescue/runs",
      playKey: "customer-rescue",
      body: { installationId: "inst-1", workObjectId: "w1", businessEntityId: "e1" },
      approvalGated: true,
    }
    state.accept.mockResolvedValue({ workObject: { id: "w1", status: "planned" }, playRunRequest: run })
    state.start.mockResolvedValue({ playRunId: "pr1", status: "awaiting_approval" })
    vi.mocked(toast.success).mockClear()
    state.entries = {
      "recommendation-feed": {
        data: {
          generatedAt: "",
          sources: { proposals: "ok" },
          items: [
            {
              id: "proposal:w1",
              kind: "proposed_work",
              title: "Review Acme for Customer Rescue",
              why: "Sentiment at risk",
              evidence: [],
              source: "account_health",
              score: 0.8,
              href: "/activity?tab=objects",
              actions: ["accept", "dismiss"],
              advisoryOnly: true,
              workObjectId: "w1",
            },
          ],
        },
      },
    }
    await render(<RecommendationFeedPanel />)
    const accept = [...host.querySelectorAll("button")].find((b) => b.textContent === "Accept")!
    await act(async () => accept.click())
    expect(state.start).not.toHaveBeenCalled()
    const options = vi.mocked(toast.success).mock.calls[0][1] as { action: { label: string; onClick: () => void } }
    expect(options.action.label).toBe("Start Play")
    await act(async () => options.action.onClick())
    expect(state.start).toHaveBeenCalledWith(run)
  })
})

describe("goal linked progress", () => {
  it("shows completion from linked work", async () => {
    state.entries = {
      "goal-linked-progress": {
        data: {
          goalId: "g1",
          basis: "linked_work",
          completionPercentage: 50,
          linkedWork: { total: 2, byStatus: { completed: 1, in_progress: 1 } },
          linkedJobs: { total: 0, byStatus: {} },
        },
      },
    }
    await render(<GoalLinkedProgress goalId="g1" />)
    expect(host.textContent).toContain("50% of linked work is done.")
    expect(host.textContent).toContain("1 in progress")
    expect(host.querySelector("a")?.getAttribute("href")).toBe("/assignments/new?goal=g1")
  })
})
