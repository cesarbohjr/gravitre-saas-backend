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

  it("soft-dedupes near-identical prediction satellites on predicts lens", () => {
    const graph = {
      nodes: [
        {
          id: "prediction:p1",
          type: "prediction",
          businessLabel:
            "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step refresh_token",
          status: "active",
          metadata: { confidence: 0.65 },
        },
        {
          id: "prediction:p2",
          type: "prediction",
          businessLabel:
            "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step authorize",
          status: "active",
          metadata: { confidence: 0.65 },
        },
        {
          id: "prediction:p3",
          type: "prediction",
          businessLabel: "Outbound reply rate may drop next week",
          status: "active",
          metadata: { confidence: 0.7 },
        },
      ],
      edges: [
        { id: "e1", type: "PREDICTS", fromId: "core:gravitre", toId: "prediction:p1" },
        { id: "e2", type: "PREDICTS", fromId: "core:gravitre", toId: "prediction:p2" },
        { id: "e3", type: "PREDICTS", fromId: "core:gravitre", toId: "prediction:p3" },
      ],
    }
    const predicts = buildTopologyFromCanonicalGraph({ graph, lens: "predicts" })
    const signals = predicts.nodes.filter((n) => n.kind === "signal")
    expect(signals).toHaveLength(2)
    expect(signals.every((n) => n.label.length <= 42)).toBe(true)
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
    expect(topology.edges[0]?.edgeType).toBe("ASSIGNED_TO")
    expect(topology.edges[0]?.state).toBe("trace")
  })

  it("styles CONTRADICTS edges with low-confidence visual state", () => {
    const graph = {
      nodes: [
        { id: "prediction:p1", type: "prediction", businessLabel: "Conflict signal", status: "active" },
        { id: "prediction:p2", type: "prediction", businessLabel: "Other signal", status: "active" },
      ],
      edges: [
        { id: "e1", type: "CONTRADICTS", fromId: "prediction:p1", toId: "prediction:p2" },
      ],
    }
    const topology = buildTopologyFromCanonicalGraph({ graph, lens: "predicts" })
    expect(topology.edges[0]?.edgeType).toBe("CONTRADICTS")
    expect(topology.edges[0]?.state).toBe("low-confidence")
    expect(topology.edges[0]?.opacity).toBeLessThan(0.5)
  })
})
