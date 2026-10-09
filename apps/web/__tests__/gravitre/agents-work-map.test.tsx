// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/agents" }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/lib/api", () => ({ agentsApi: { update: vi.fn(), stop: vi.fn(), start: vi.fn() } }))
vi.mock("@/components/gravitre/goal-workflow-wizard", () => ({ GoalWorkflowWizard: () => null }))

import { DORMANT_CAP, RosterWorkMap } from "@/components/agents/roster/roster-work-map"
import {
  buildWorkMap,
  missingPieces,
  toRosterAgent,
  wiredAgentIds,
  type RosterStatsPayload,
} from "@/lib/agents-roster"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
// Radix and framer-motion probe these in jsdom.
window.matchMedia ??= ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false })) as unknown as typeof window.matchMedia

let root: Root | null = null
let host: HTMLDivElement | null = null
function render(ui: React.ReactElement): HTMLDivElement {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  act(() => root!.render(ui))
  return host
}
afterEach(() => {
  act(() => root?.unmount())
  host?.remove()
  root = null
  host = null
})

const idle = { tasksToday: 0, failedToday: 0, runningNow: 0, successRateToday: null, successRate7d: null, lastActiveAt: null, daily: [], blocked: null }
const stats: RosterStatsPayload = {
  generatedAt: "",
  days: [],
  agents: { scout: idle, enrich: idle },
  approvalGate: {},
  goals: [{ id: "g1", objective: "Get 100 MSP leads", status: "active", department: "Sales", priority: "high", connectedSystems: ["apollo"], agentIds: ["scout", "enrich"] }],
}
const raw = [
  { id: "scout", name: "Lead Scouting Analyst", role: "Analyst", department: "Sales", description: "Finds accounts that match your ideal customer.", permissions: ["apollo"] },
  { id: "enrich", name: "Lead Enrichment Coordinator", role: "SDR", department: "Sales", description: "Fills in contact details.", permissions: [] },
  { id: "mkt", name: "Marketing Agent", role: "Marketing", department: "Marketing", description: "Runs campaigns.", permissions: ["hubspot"] },
  ...Array.from({ length: 8 }, (_, i) => ({ id: `ph${i}`, name: `[Placeholder ${i}]`, department: "General", description: "AI teammate" })),
]
const agents = raw.map((r) => toRosterAgent(r, stats))

describe("work map wiring", () => {
  it("only counts agents with a connector, an output and a goal as wired", () => {
    const model = buildWorkMap(agents, stats.goals)
    expect([...wiredAgentIds(model)]).toEqual(["scout"])
    const byId = new Map(agents.map((a) => [a.id, a]))
    expect(missingPieces(byId.get("enrich")!, model)).toEqual(["a connector"])
    expect(missingPieces(byId.get("mkt")!, model)).toEqual(["a goal"])
    expect(missingPieces(byId.get("ph0")!, model)).toEqual(["instructions", "a connector", "an output", "a goal"])
  })

  it("draws wired agents in the lanes and caps the dormant group", () => {
    const el = render(<RosterWorkMap agents={agents} goals={stats.goals} statsAvailable onGoalsChanged={() => {}} />)
    const laneCards = [...el.querySelectorAll("button.wm-card")].map((b) => b.textContent ?? "")
    expect(laneCards.some((t) => t.includes("Lead Scouting Analyst"))).toBe(true)
    expect(laneCards.some((t) => t.includes("Marketing Agent"))).toBe(false)
    const dormant = el.querySelector(".wm-dormant")!
    expect(dormant.textContent).toContain("Dormant · 10")
    expect(dormant.querySelectorAll("button.wm-grow")).toHaveLength(DORMANT_CAP)
    expect(dormant.querySelector("a")?.getAttribute("href")).toBe("/agents?view=list")
    // Lines are drawn for wired agents only: one app link, one output link, one goal link.
    expect(el.querySelectorAll("path.wm-link")).toHaveLength(3)
    // Apps only dormant agents use sit apart, with no lines.
    expect(el.querySelector(".wm-group:not(.wm-dormant)")?.textContent).toContain("HubSpot")
  })

  it("opens a detail sheet for agents, connectors, outputs and goals", () => {
    const el = render(<RosterWorkMap agents={agents} goals={stats.goals} statsAvailable onGoalsChanged={() => {}} />)
    const open = (label: RegExp) => {
      const btn = [...el.querySelectorAll<HTMLButtonElement>("button.wm-card, button.wm-grow")].find((b) => label.test(b.textContent ?? ""))!
      act(() => btn.click())
      return document.body.querySelector('[role="dialog"]')?.textContent ?? ""
    }
    expect(open(/Lead Scouting Analyst/)).toContain("Fully connected")
    expect(open(/Marketing Agent/)).toContain("Dormant. It still needs a goal")
    expect(open(/Apollo/)).toContain("Agents that use it")
    expect(open(/Qualified leads/)).toContain("Produced by")
    expect(open(/Get 100 MSP leads/)).toContain("Agents feeding it")
  })
})
