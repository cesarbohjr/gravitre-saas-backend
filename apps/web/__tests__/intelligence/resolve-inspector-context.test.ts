import { describe, expect, it } from "vitest"
import {
  matchPriorityEvidence,
  resolveInspectorContext,
} from "@/lib/intelligence/resolve-inspector-context"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { Agent } from "@/types/api"

const pageContext: IntelligencePageContextResponse = {
  snapshot: {
    generatedAt: "2026-09-13T12:00:00Z",
    tenantId: "org-1",
    timeWindowHours: 24,
    coreState: "flow-inward",
    agents: [
      {
        id: "a1",
        name: "Lead Scouting Analyst",
        role: "SDR",
        department: "Sales",
        businessLabel: "Lead Scouting Analyst",
        configuredStatus: "active",
        executionStatus: "idle",
        isConfiguredActive: true,
        isCurrentlyRunning: false,
      },
    ],
    predictions: [
      {
        id: "p1",
        businessStatement: "OAuth token expiring soon",
        confidence: 0.82,
        department: "sales",
        evidence: ["HubSpot connector token expires in 3 days"],
        qualityFlags: ["UNSCOPED_PREDICTION"],
        source: { system: "business_signals_engine", recordId: "p1" },
      },
    ],
    learnings: [
      {
        id: "l1",
        businessStatement: "Enterprise deals close faster with multi-threading",
        evidence: ["3 won deals in Q3 used multi-thread outreach"],
        source: { system: "memory_promotion", recordId: "l1" },
      },
    ],
    metrics: {
      knowledge: {},
      learning: {},
      predictions: {},
      execution: {},
      outcomes: {},
    },
    qualityFlags: [],
    departments: [],
  },
  graph: {
    nodes: [],
    edges: [{ id: "e1", type: "EVIDENCE_FOR", fromId: "agent:a1", toId: "prediction:p1" }],
  },
  activeLens: "acts",
  availableLenses: ["knows", "learns", "predicts", "acts", "improves"],
  metrics: {
    knowledge: {},
    learning: {},
    predictions: {},
    execution: {},
    outcomes: {},
  },
  qualityFlags: [],
  suggestedQuestions: [],
}

const agent: Agent = {
  id: "a1",
  name: "Lead Scouting Analyst",
  role: "SDR",
  department: "Sales",
  description: "",
  status: "active",
  personality: { color: "", gradient: "", glow: "" },
  stats: { tasksCompleted: 0, successRate: 0, avgResponseTime: 0 },
  capabilities: [],
  permissions: [],
  lastAction: "",
  lastActionTime: "",
}

describe("resolveInspectorContext", () => {
  it("returns canonical agent execution vs configured distinction", () => {
    const ctx = resolveInspectorContext({ kind: "agent", agent }, pageContext)
    expect(ctx?.title).toBe("Lead Scouting Analyst")
    expect(ctx?.facts.some((f) => f.label === "Roster status" && f.value.includes("active"))).toBe(
      true,
    )
    expect(ctx?.facts.some((f) => f.label === "Execution" && f.value.includes("Idle"))).toBe(true)
  })

  it("resolves edge selection with relationship context", () => {
    const ctx = resolveInspectorContext(
      { kind: "edge", edgeId: "e1", label: "EVIDENCE_FOR" },
      pageContext,
    )
    expect(ctx?.eyebrow).toBe("Relationship")
    expect(ctx?.summary).toContain("agent:a1")
    expect(ctx?.askPrompt).toContain("connect")
  })

  it("surfaces prediction evidence and quality flags for signals", () => {
    const ctx = resolveInspectorContext(
      {
        kind: "signal",
        signal: { id: "p1", title: "OAuth token expiring soon", summary: "HubSpot" },
      },
      pageContext,
    )
    expect(ctx?.evidence).toContain("HubSpot connector token expires in 3 days")
    expect(ctx?.qualityFlags.some((f) => f.includes("connected source"))).toBe(true)
    expect(ctx?.facts.some((f) => f.label === "Confidence" && f.value === "82%")).toBe(true)
  })
})

describe("matchPriorityEvidence", () => {
  it("matches priority item by signal title", () => {
    const item = matchPriorityEvidence(
      {
        departments: [
          {
            department: "sales",
            priorities: [
              {
                workObjectId: "wo-1",
                title: "OAuth token expiring soon",
                priorityScore: 88,
                signalContributions: [],
              },
            ],
          },
        ],
      },
      { signalTitle: "OAuth token expiring" },
    )
    expect(item?.workObjectId).toBe("wo-1")
  })
})
