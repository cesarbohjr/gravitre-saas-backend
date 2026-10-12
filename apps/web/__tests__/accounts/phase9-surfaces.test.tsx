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
  refresh: vi.fn(),
}))

vi.mock("swr", () => ({
  default: (key: string | string[] | null) => ({
    ...(key ? state.entries[Array.isArray(key) ? key[0] : key] : {}),
    mutate: state.refresh,
  }),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))
vi.mock("@/lib/api", () => ({
  accountIntelligenceApi: { acceptProposal: state.accept, dismissProposal: state.dismiss },
  isFeatureOff: (e: unknown) => typeof e === "object" && e !== null && (e as { status?: number }).status === 404,
}))

import { AccountHealthPanel } from "@/components/accounts/account-health-panel"
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

describe("switched off", () => {
  it("renders nothing for each surface", async () => {
    state.entries = {
      "account-health-list": { error: off },
      "recommendation-feed": { error: off },
      "goal-linked-progress": { error: off },
    }
    await render(
      <>
        <AccountHealthPanel />
        <RecommendationFeedPanel />
        <GoalLinkedProgress goalId="g1" />
      </>,
    )
    expect(host.textContent).toBe("")
  })
})

describe("account health", () => {
  it("lists flagged signals and opens the per-signal rules with evidence", async () => {
    state.entries = {
      "account-health-list": {
        data: { accounts: [{ entity: { id: "e1", name: "Acme", systems: [] }, statusCounts: {}, atRisk: ["Customer sentiment"], watch: [] }] },
      },
      "account-health": {
        data: {
          entity: { id: "e1", name: "Acme", systems: [] },
          compositeScore: null,
          statusCounts: {},
          generatedAt: "",
          dimensions: [
            {
              key: "sentiment",
              label: "Customer sentiment",
              kind: "leading",
              definition: "Tone of inbound customer messages over 30 days.",
              status: "at_risk",
              value: { direction: "falling" },
              note: null,
              evidence: ['"we are very unhappy" (zendesk, 2026-10-10)'],
              coverage: {},
            },
          ],
        },
      },
    }
    await render(<AccountHealthPanel />)
    expect(host.textContent).toContain("Acme")
    expect(host.textContent).toContain("Customer sentiment")
    await act(async () => host.querySelector<HTMLButtonElement>("button[aria-expanded]")!.click())
    expect(host.textContent).toContain("There is no single health score")
    expect(host.textContent).toContain("we are very unhappy")
    expect(host.textContent).toContain("At risk")
    expect(host.textContent).toContain("Tone of inbound customer messages")
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
  })
})
