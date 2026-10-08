import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import {
  buildWorkMap,
  deriveOutput,
  formatLastActive,
  groupByDepartment,
  litAgents,
  standoutAgent,
  toRosterAgent,
  traceStory,
  type RosterStatsPayload,
} from "@/lib/agents-roster"

const stats: RosterStatsPayload = {
  generatedAt: "2026-10-08T12:00:00Z",
  days: [],
  agents: {
    scout: {
      tasksToday: 0, failedToday: 0, runningNow: 0, successRateToday: null, successRate7d: null,
      lastActiveAt: null, daily: [], blocked: null,
    },
    enrich: {
      tasksToday: 0, failedToday: 1, runningNow: 0, successRateToday: 0, successRate7d: 0,
      lastActiveAt: "2026-10-08T10:00:00Z", daily: [],
      blocked: { kind: "failed", reason: "Waiting on an Apollo plan with search access", jobId: "j1", at: "2026-10-08T10:00:00Z" },
    },
    mkt: {
      tasksToday: 9, failedToday: 0, runningNow: 0, successRateToday: 100, successRate7d: 96,
      lastActiveAt: "2026-10-08T11:00:00Z", daily: [1, 2, 9], blocked: null,
    },
  },
  approvalGate: { mkt: false },
  goals: [
    { id: "g1", objective: "Get 100 MSP leads", status: "draft", department: "Sales", priority: "medium", connectedSystems: [], agentIds: ["scout", "enrich"] },
  ],
}

const raw = [
  { id: "scout", name: "Lead Scouting Analyst", role: "Analyst", department: "Sales", description: "Finds accounts that match your ideal customer.", permissions: ["apollo"] },
  { id: "enrich", name: "Lead Enrichment Coordinator", role: "Sales Development", department: "Sales", description: "Fills in company and contact details.", permissions: ["apollo", "hubspot"] },
  { id: "mkt", name: "Marketing Agent", role: "Marketing Operations", department: "Marketing", description: "Runs campaigns and sequences.", permissions: ["hubspot", "slack"], model: "claude-sonnet" },
  { id: "ph", name: "[General agent]", role: "", department: "General", description: "AI teammate" },
]

const agents = raw.map((r) => toRosterAgent(r, stats))

describe("agents roster view model", () => {
  it("joins agents with real job stats and never invents numbers", () => {
    const [scout, enrich, mkt, ph] = agents
    expect(scout.state).toBe("ready")
    expect(scout.success7d).toBeNull()
    expect(enrich.state).toBe("blocked")
    expect(mkt.state).toBe("active_today")
    expect(mkt.tasksToday).toBe(9)
    expect(ph.state).toBe("not_set_up")
    expect(ph.output).toBeNull()
    // No stats payload: no tasks, no rates.
    const bare = toRosterAgent(raw[2], undefined)
    expect(bare.tasksToday).toBe(0)
    expect(bare.successToday).toBeNull()
  })

  it("gates writes by policy and fails closed", () => {
    const [scout, , mkt, ph] = agents
    expect(scout.gated).toBe(true) // no identity record
    expect(mkt.gated).toBe(false) // explicitly auto-run
    expect(ph.gated).toBe(false) // no app to write to
  })

  it("derives what each agent produces from its role", () => {
    expect(agents[0].output).toBe("Qualified leads")
    expect(agents[1].output).toBe("Enriched contacts")
    expect(agents[2].output).toBe("Campaigns sent")
    expect(deriveOutput("Helper", "", "", ["summarize_docs"])).toBe("Summarize docs")
  })

  it("groups departments, picks the standout and formats activity", () => {
    expect(groupByDepartment(agents).map((g) => g.meta.id)).toEqual(["sales", "marketing", "general"])
    expect(standoutAgent(agents)?.id).toBe("mkt")
    expect(standoutAgent(agents.filter((a) => a.id !== "mkt"))).toBeNull()
    expect(formatLastActive(null)).toBe("No runs yet")
  })

  it("builds the work map with goal paths and a story from live data", () => {
    const map = buildWorkMap(agents, stats.goals)
    expect(map.apps.map((a) => a.name).sort()).toEqual(["Apollo.io", "HubSpot", "Slack"].sort())
    expect(map.goalAgents.get("g1")).toEqual(["scout", "enrich"])
    expect(map.unmeasuredOutputs.map((o) => o.name)).toEqual(["Campaigns sent"])
    expect([...litAgents(map, "goal:g1")].sort()).toEqual(["enrich", "scout"])
    const story = traceStory(map, "goal:g1")
    expect(story).toContain("Two agents feed Get 100 MSP leads")
    expect(story).toContain("Lead Enrichment Coordinator is blocked")
  })

  it("roster page keeps view in the URL and wires the real endpoints", () => {
    const page = readFileSync(resolve(__dirname, "../../app/(app)/agents/page.tsx"), "utf8")
    expect(page).toMatch(/searchParams\.get\("view"\)/)
    expect(page).toMatch(/rosterStatsKey/)
    const list = readFileSync(resolve(__dirname, "../../components/agents/roster/roster-list-view.tsx"), "utf8")
    expect(list).toMatch(/agentsApi\.update/)
    expect(list).toMatch(/agentsApi\.stop/)
  })
})
