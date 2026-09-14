import type { IntelligenceCoreStateResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  buildMapTopology,
  CORE_ID,
  type MapEdge,
  type MapNode,
  type MapTopology,
} from "@/components/intelligence/map/map-topology"
import {
  buildTopologyFromCanonicalGraph,
  type CanonicalGraphEdge,
  type CanonicalGraphNode,
} from "@/lib/intelligence/canonical-graph-topology"
import type { GraphRenderModel } from "./types"
import { GraphLayoutEngine } from "./graph-layout-engine"

export type IntelligenceGraphInput = {
  lens: IntelligenceMapLens
  canonicalGraph?: { nodes: Record<string, unknown>[]; edges: Record<string, unknown>[] } | null
  agents?: Agent[] | null
  entityTypes?: string[] | null
  readiness?: Record<string, unknown> | null
  orgTraining?: Record<string, { artifact_loaded?: boolean }> | null
  signals?: Record<string, unknown>[] | null
  coreState?: IntelligenceCoreStateResponse | null
  cacheKey?: string
  pinnedPositions?: Map<string, { x: number; y: number }>
  collapsedClusterIds?: Set<string>
}

/**
 * I2 — data + semantics layer. Topology projection lives here, not in renderers.
 */
export class IntelligenceGraph {
  readonly topology: MapTopology
  readonly lens: IntelligenceMapLens
  private readonly layoutEngine = new GraphLayoutEngine()

  constructor(input: IntelligenceGraphInput) {
    this.lens = input.lens
    this.topology = IntelligenceGraph.buildTopology(input)
  }

  static buildTopology(input: IntelligenceGraphInput): MapTopology {
    if (input.canonicalGraph?.nodes?.length) {
      return buildTopologyFromCanonicalGraph({
        graph: input.canonicalGraph as {
          nodes: CanonicalGraphNode[]
          edges: CanonicalGraphEdge[]
        },
        lens: input.lens,
        agents: input.agents,
      })
    }
    if (!input.coreState) {
      return { nodes: [], edges: [], caption: "" }
    }
    return buildMapTopology({
      lens: input.lens,
      departments: input.coreState.departments,
      agents: input.agents,
      entityTypes: input.entityTypes,
      readiness: input.readiness,
      orgTraining: input.orgTraining,
      signals: input.signals,
      coreState: input.coreState.core.state,
    })
  }

  get nodes(): MapNode[] {
    return this.topology.nodes
  }

  get edges(): MapEdge[] {
    return this.topology.edges
  }

  get caption(): string {
    return this.topology.caption
  }

  buildRenderModel(options: {
    cacheKey?: string
    pinnedPositions?: Map<string, { x: number; y: number }>
    collapsedClusterIds?: Set<string>
  } = {}): GraphRenderModel {
    const layout = this.layoutEngine.computeLayout({
      nodes: this.topology.nodes,
      edges: this.topology.edges,
      lens: this.lens,
      cacheKey: options.cacheKey,
      pinnedPositions: options.pinnedPositions,
      collapsedClusterIds: options.collapsedClusterIds,
    })
    return {
      topology: this.topology,
      layout,
      lens: this.lens,
      caption: this.topology.caption,
    }
  }

  nodeById(id: string): MapNode | undefined {
    return this.topology.nodes.find((node) => node.id === id)
  }

  edgeById(id: string): MapEdge | undefined {
    return this.topology.edges.find((edge) => edge.id === id)
  }

  connectedNodeIds(nodeId: string): Set<string> {
    const ids = new Set<string>()
    for (const edge of this.topology.edges) {
      if (edge.fromId === nodeId || edge.toId === nodeId) {
        ids.add(edge.fromId === CORE_ID ? edge.toId : edge.fromId)
        ids.add(edge.toId === CORE_ID ? edge.fromId : edge.toId)
      }
      if (edge.fromId === nodeId) ids.add(edge.toId)
      if (edge.toId === nodeId) ids.add(edge.fromId)
    }
    ids.delete(CORE_ID)
    return ids
  }

  filterNodesByKind(kinds: Set<MapNode["kind"]> | null): MapNode[] {
    if (!kinds || kinds.size === 0) return this.topology.nodes
    return this.topology.nodes.filter((node) => kinds.has(node.kind))
  }

  searchNodes(query: string): MapNode[] {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return this.topology.nodes.filter(
      (node) =>
        node.label.toLowerCase().includes(q) ||
        (node.sublabel?.toLowerCase().includes(q) ?? false) ||
        node.id.toLowerCase().includes(q),
    )
  }
}

export { CORE_ID }
