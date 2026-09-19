/**
 * Relational Topology — Intelligence Core geometry by state.
 * Deterministic layouts (no random). LEARN increases edge count permanently in-session.
 */

import type { CoreState } from "@/components/marketing/system/department-network/types"

export type TopologyPoint = { x: number; y: number }
export type TopologyEdge = [number, number]

export type TopologyLayout = {
  nodes: TopologyPoint[]
  edges: TopologyEdge[]
  /** Inbound ghost node for receiving (index into nodes, or -1) */
  inboundIndex: number
  /** Outbound spoke tip indices for coordinating */
  outboundIndices: number[]
}

const CX = 40
const CY = 36

function ring(n: number, r: number, startDeg = -90): TopologyPoint[] {
  const out: TopologyPoint[] = []
  for (let i = 0; i < n; i++) {
    const a = ((startDeg + (360 / n) * i) * Math.PI) / 180
    out.push({ x: CX + Math.cos(a) * r, y: CY + Math.sin(a) * r })
  }
  return out
}

/** Stable idle: 5 nodes, 5 cycle edges + 1 chord */
function idleLayout(): TopologyLayout {
  const nodes = [{ x: CX, y: CY }, ...ring(5, 18)]
  const edges: TopologyEdge[] = [
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 1],
    [1, 3],
    [0, 1],
    [0, 3],
  ]
  return { nodes, edges, inboundIndex: -1, outboundIndices: [] }
}

function receivingLayout(): TopologyLayout {
  const base = idleLayout()
  const inbound = { x: CX - 28, y: CY }
  const nodes = [...base.nodes, inbound]
  const inboundIndex = nodes.length - 1
  return {
    nodes,
    edges: [...base.edges, [inboundIndex, 0]],
    inboundIndex,
    outboundIndices: [],
  }
}

function connectingLayout(): TopologyLayout {
  const base = idleLayout()
  return {
    ...base,
    edges: [...base.edges, [0, 2], [0, 4], [2, 4]],
    inboundIndex: -1,
    outboundIndices: [],
  }
}

function coordinatingLayout(): TopologyLayout {
  const nodes = [{ x: CX, y: CY }, ...ring(5, 16), ...ring(3, 28, -60)]
  const edges: TopologyEdge[] = [
    [0, 1],
    [0, 2],
    [0, 3],
    [0, 4],
    [0, 5],
    [1, 2],
    [2, 3],
    [0, 6],
    [0, 7],
    [0, 8],
  ]
  return { nodes, edges, inboundIndex: -1, outboundIndices: [6, 7, 8] }
}

function verifyingLayout(): TopologyLayout {
  const nodes = [{ x: CX, y: CY }, ...ring(4, 14)]
  const edges: TopologyEdge[] = [
    [0, 1],
    [0, 2],
    [0, 3],
    [0, 4],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 1],
  ]
  return { nodes, edges, inboundIndex: -1, outboundIndices: [] }
}

function learningLayout(): TopologyLayout {
  const nodes = [{ x: CX, y: CY }, ...ring(6, 18)]
  const edges: TopologyEdge[] = [
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 1],
    [0, 1],
    [0, 3],
    [0, 5],
    [1, 4], // new learned chord
  ]
  return { nodes, edges, inboundIndex: -1, outboundIndices: [] }
}

/** Learned idle: denser than idle (system remembered) */
function learnedLayout(): TopologyLayout {
  const nodes = [{ x: CX, y: CY }, ...ring(6, 17)]
  const edges: TopologyEdge[] = [
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 6],
    [6, 1],
    [0, 1],
    [0, 2],
    [0, 4],
    [0, 5],
    [1, 4],
    [2, 5],
  ]
  return { nodes, edges, inboundIndex: -1, outboundIndices: [] }
}

export function topologyForCoreState(state: CoreState): TopologyLayout {
  switch (state) {
    case "receiving":
      return receivingLayout()
    case "connecting":
    case "reasoning":
      return connectingLayout()
    case "coordinating":
    case "acting":
      return coordinatingLayout()
    case "verifying":
    case "verified":
      return verifyingLayout()
    case "learning":
      return learningLayout()
    case "learned":
      return learnedLayout()
    case "idle":
    default:
      return idleLayout()
  }
}

export function topologyEdgeCount(state: CoreState): number {
  return topologyForCoreState(state).edges.length
}
