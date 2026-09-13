import { describe, expect, it } from "vitest"
import { resolveAskMapFocus } from "@/components/intelligence/map/resolve-ask-map-focus"
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
  {
    id: "support",
    eventsInWindow: 1,
    recentInflow: 0,
    recentResolved: 0,
    confidence: null,
    state: "idle",
  },
]

const agents: Agent[] = [
  {
    id: "a1",
    name: "Sales Agent",
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

describe("resolveAskMapFocus", () => {
  it("routes attention questions to predicts lens and matching signals", () => {
    const focus = resolveAskMapFocus("What needs attention with HubSpot OAuth?", {
      departments,
      agents,
      signals: [
        {
          id: "sig-1",
          title: "OAuth token expiring soon",
          summary: "HubSpot connector token expires",
        },
      ],
    })
    expect(focus.lens).toBe("predicts")
    expect(focus.highlightNodeIds.length).toBeGreaterThan(0)
    expect(focus.selection?.kind).toBe("signal")
  })

  it("highlights sales department when question mentions sales slowing", () => {
    const focus = resolveAskMapFocus("Why are sales slowing down?", {
      departments,
      agents,
      signals: [],
    })
    expect(focus.highlightNodeIds).toContain("dept:sales")
    expect(focus.selection?.kind).toBe("department")
  })

  it("uses acts lens for agent questions", () => {
    const focus = resolveAskMapFocus("What agents are currently active?", {
      departments,
      agents,
      signals: [],
    })
    expect(focus.lens).toBe("acts")
    expect(focus.highlightNodeIds).toContain("agent:a1")
  })
})
