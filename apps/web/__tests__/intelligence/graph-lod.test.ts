import { describe, expect, it } from "vitest"
import { GraphLayoutEngine } from "@/lib/intelligence/graph/graph-layout-engine"
import { CLUSTER_THRESHOLD } from "@/lib/intelligence/graph/types"
import type { MapNode } from "@/components/intelligence/map/map-topology"
import {
  isDenseGraph,
  resolveNodeCollisions,
  shouldShowNodeLabel,
} from "@/lib/intelligence/graph/graph-lod"

function agentNodes(count: number): MapNode[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `agent:${i}`,
    kind: "agent" as const,
    label: `Agent ${i}`,
    emphasis: 0.5,
  }))
}

describe("I13 graph LOD", () => {
  it("treats graphs at the cluster threshold as dense", () => {
    expect(isDenseGraph(CLUSTER_THRESHOLD - 1)).toBe(false)
    expect(isDenseGraph(CLUSTER_THRESHOLD)).toBe(true)
  })

  it("hides labels below LOD scale unless selected", () => {
    expect(shouldShowNodeLabel({ scale: 0.4, dense: false })).toBe(false)
    expect(shouldShowNodeLabel({ scale: 0.4, dense: false, selected: true })).toBe(true)
    expect(shouldShowNodeLabel({ scale: 0.9, dense: true })).toBe(false)
    expect(shouldShowNodeLabel({ scale: 1.1, dense: true })).toBe(true)
  })

  it("separates colliding node centers", () => {
    const positions = new Map([
      ["a", { x: 100, y: 100 }],
      ["b", { x: 102, y: 100 }],
    ])
    const next = resolveNodeCollisions(positions, 40, 12)
    const a = next.get("a")!
    const b = next.get("b")!
    expect(Math.hypot(b.x - a.x, b.y - a.y)).toBeGreaterThanOrEqual(39)
  })

  it("auto-collapses kind clusters above density and expands on request", () => {
    const engine = new GraphLayoutEngine()
    const nodes = agentNodes(CLUSTER_THRESHOLD + 2)
    const collapsed = engine.computeLayout({
      nodes,
      edges: [],
      lens: "acts",
    })
    expect(collapsed.clusters.length).toBeGreaterThan(0)
    expect(collapsed.clusters.every((c) => c.collapsed)).toBe(true)
    const clusterId = collapsed.clusters[0]!.id
    const expanded = engine.computeLayout({
      nodes,
      edges: [],
      lens: "acts",
      expandedClusterIds: new Set([clusterId]),
    })
    expect(expanded.clusters.find((c) => c.id === clusterId)?.collapsed).toBe(false)
  })
})
