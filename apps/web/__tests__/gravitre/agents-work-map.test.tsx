// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/agents" }))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock("@/lib/api", () => ({ agentsApi: { update: vi.fn(), stop: vi.fn(), start: vi.fn() } }))
vi.mock("@/components/gravitre/goal-workflow-wizard", () => ({ GoalWorkflowWizard: () => null }))

import { RosterWorkMap } from "@/components/agents/roster/roster-work-map"
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

  it("draws every agent in the lanes, grouped by department, and dims what is off the trace", () => {
    const el = render(<RosterWorkMap agents={agents} goals={stats.goals} statsAvailable onGoalsChanged={() => {}} />)
    const laneCards = [...el.querySelectorAll<HTMLButtonElement>("button.wm-card")]
    const named = (re: RegExp) => laneCards.find((b) => re.test(b.textContent ?? ""))
    expect(named(/Lead Scouting Analyst/)?.classList.contains("dim")).toBe(false)
    expect(named(/Marketing Agent/)?.classList.contains("dim")).toBe(true)
    expect(el.querySelector(".wm-dormant")).toBeNull()
    // Agents with no connector get one note under the apps lane.
    const noApp = el.querySelector(".wm-nodata")!
    expect(noApp.textContent).toContain("No app connected")
    expect(noApp.querySelector("a")?.getAttribute("href")).toBe("/connectors")
    // Status pills count agent states.
    const pills = el.querySelector(".wm-counts")?.textContent ?? ""
    expect(pills).toMatch(/\d+ working/)
    expect(pills).toMatch(/\d+ ready/)
    expect(pills).toMatch(/\d+ not set up/)
  })

  it("shows a goal's stored start and target on its card", () => {
    const goals = [{ ...stats.goals[0], status: "draft", successMetrics: { metric: "MSP leads", start: 0, target: 100 } }]
    const el = render(<RosterWorkMap agents={agents} goals={goals} statsAvailable onGoalsChanged={() => {}} />)
    const card = el.querySelector(".wm-goal")!
    expect(card.textContent).toContain("0 of 100 MSP leads")
    expect(card.querySelector('[role="progressbar"]')).toBeTruthy()
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
