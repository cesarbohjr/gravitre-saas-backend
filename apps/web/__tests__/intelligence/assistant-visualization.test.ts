import { describe, expect, it } from "vitest"
import {
  applyAssistantVisualizationToMapState,
  filterNodeIdsToGraph,
  parseAssistantVisualization,
} from "@/lib/intelligence/assistant-visualization"
import type { IntelligenceCoreDepartment } from "@/lib/api"
import type { Agent } from "@/types/api"

const departments: IntelligenceCoreDepartment[] = [
  {
    id: "sales",
    eventsInWindow: 2,
    recentInflow: 1,
    recentResolved: 0,
    confidence: 0.4,
    state: "trace",
  },
]

const agents: Agent[] = [
  {
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
  },
]

describe("parseAssistantVisualization", () => {
  it("parses canonical agent visualization from SSE payload", () => {
    const viz = parseAssistantVisualization({
      lens: "acts",
      highlightNodeIds: ["agent:a1", "agent:a2"],
      focusNodeIds: ["agent:a1"],
      dimNodeIds: ["agent:a3"],
      timeWindowHours: 24,
    })
    expect(viz?.lens).toBe("acts")
    expect(viz?.highlightNodeIds).toEqual(["agent:a1", "agent:a2"])
    expect(viz?.focusNodeIds).toEqual(["agent:a1"])
    expect(viz?.dimNodeIds).toEqual(["agent:a3"])
  })

  it("returns null for empty visualization objects", () => {
    expect(parseAssistantVisualization({})).toBeNull()
    expect(parseAssistantVisualization(null)).toBeNull()
  })
})

describe("filterNodeIdsToGraph", () => {
  it("drops node ids not present in canonical graph", () => {
    const graphIds = new Set(["agent:a1", "prediction:p1"])
    expect(filterNodeIdsToGraph(["agent:a1", "agent:missing"], graphIds)).toEqual(["agent:a1"])
  })
})

describe("applyAssistantVisualizationToMapState", () => {
  it("maps agent focus to acts lens selection", () => {
    const state = applyAssistantVisualizationToMapState(
      {
        lens: "acts",
        highlightNodeIds: ["agent:a1"],
        focusNodeIds: ["agent:a1"],
        dimNodeIds: ["agent:a2"],
      },
      {
        graphNodeIds: new Set(["agent:a1", "agent:a2"]),
        agents,
        departments,
        signals: [],
      },
    )
    expect(state.lens).toBe("acts")
    expect(state.highlightNodeIds).toEqual(["agent:a1"])
    expect(state.dimNodeIds).toEqual(["agent:a2"])
    expect(state.selection?.kind).toBe("agent")
    if (state.selection?.kind === "agent") {
      expect(state.selection.agent.id).toBe("a1")
    }
  })

  it("resolves prediction nodes to signal selection", () => {
    const state = applyAssistantVisualizationToMapState(
      {
        lens: "predicts",
        highlightNodeIds: ["prediction:p1"],
        focusNodeIds: ["prediction:p1"],
      },
      {
        graphNodeIds: new Set(["prediction:p1"]),
        agents: [],
        departments: [],
        signals: [{ id: "p1", title: "OAuth expiring", summary: "HubSpot token" }],
      },
    )
    expect(state.lens).toBe("predicts")
    expect(state.selection?.kind).toBe("signal")
  })
})
