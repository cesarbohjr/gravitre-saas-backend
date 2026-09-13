import { describe, expect, it } from "vitest"
import { buildTopologyFromCanonicalGraph } from "@/lib/intelligence/canonical-graph-topology"

describe("buildTopologyFromCanonicalGraph", () => {
  it("maps agents and predictions from canonical graph for ACTS vs PREDICTS lenses", () => {
    const graph = {
      nodes: [
        { id: "core:gravitre", type: "core", businessLabel: "Gravitre Intelligence", status: "idle" },
        { id: "agent:a1", type: "agent", businessLabel: "Email Campaign Reporting Agent", status: "active", metadata: { isConfiguredActive: true, isCurrentlyRunning: false } },
        { id: "prediction:p1", type: "prediction", businessLabel: "OAuth token expiring", status: "active", metadata: { confidence: 0.82 } },
      ],
      edges: [
        { id: "e1", type: "ASSIGNED_TO", fromId: "core:gravitre", toId: "agent:a1" },
        { id: "e2", type: "PREDICTS", fromId: "core:gravitre", toId: "prediction:p1" },
      ],
    }

    const acts = buildTopologyFromCanonicalGraph({ graph, lens: "acts" })
    expect(acts.nodes.some((n) => n.kind === "agent")).toBe(true)
    expect(acts.nodes.some((n) => n.label.includes("Email Campaign"))).toBe(true)

    const predicts = buildTopologyFromCanonicalGraph({ graph, lens: "predicts" })
    expect(predicts.nodes.some((n) => n.kind === "signal")).toBe(true)
    expect(predicts.nodes.some((n) => n.label.includes("OAuth"))).toBe(true)
  })

  it("remaps core:gravitre to __core__ for edge rendering", () => {
    const graph = {
      nodes: [
        { id: "agent:a1", type: "agent", businessLabel: "Test Agent", status: "active" },
      ],
      edges: [{ id: "e1", type: "ASSIGNED_TO", fromId: "core:gravitre", toId: "agent:a1" }],
    }
    const topology = buildTopologyFromCanonicalGraph({ graph, lens: "acts" })
    expect(topology.edges[0]?.fromId).toBe("__core__")
  })
})
