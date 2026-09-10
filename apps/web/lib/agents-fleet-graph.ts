/**
 * Build honest fleet GRAPH edges from real agent + swarm data.
 * Does not invent collaborates/escalates/fixture HubSpot links.
 */

import type {
  FleetAgent,
  FleetEdge,
  FleetGraphExtraNode,
} from "@/components/agents/fleet-v4/types"
import type { AgentSwarmRun } from "@/types/api"

const CONNECTOR_PREFIX = "conn:"

export function connectorNodeId(name: string): string {
  return `${CONNECTOR_PREFIX}${name.trim().toLowerCase().replace(/\s+/g, "-")}`
}

export function buildConnectorEdges(agents: FleetAgent[]): {
  edges: FleetEdge[]
  nodes: FleetGraphExtraNode[]
} {
  const nodeMap = new Map<string, FleetGraphExtraNode>()
  const edges: FleetEdge[] = []

  for (const agent of agents) {
    const systems = agent.connectedSystems ?? []
    for (const name of systems) {
      const label = String(name ?? "").trim()
      if (!label) continue
      const id = connectorNodeId(label)
      if (!nodeMap.has(id)) {
        nodeMap.set(id, { id, kind: "connector", label })
      }
      edges.push({
        id: `uses-${agent.id}-${id}`,
        source: agent.id,
        target: id,
        kind: "uses_connector",
        label: "uses",
      })
    }
  }

  return { edges, nodes: [...nodeMap.values()] }
}

export function buildParentEdges(agents: FleetAgent[]): FleetEdge[] {
  const ids = new Set(agents.map((a) => a.id))
  const edges: FleetEdge[] = []
  for (const agent of agents) {
    const parentId = agent.parentAgentId
    if (!parentId || !ids.has(parentId) || parentId === agent.id) continue
    edges.push({
      id: `parent-${parentId}-${agent.id}`,
      source: parentId,
      target: agent.id,
      kind: "parent_of",
      label: "parent",
    })
  }
  return edges
}

const ACTIVE_SWARM = new Set([
  "pending",
  "running",
  "aggregating",
  "in_progress",
  "active",
  "executing",
])

export function isActiveSwarmStatus(status: string | null | undefined): boolean {
  return ACTIVE_SWARM.has(String(status ?? "").toLowerCase())
}

/** Swarm parent → subtask agents. Mark active when the run is in-flight. */
export function buildSwarmEdges(
  runs: AgentSwarmRun[],
  agentIds: Set<string>,
): FleetEdge[] {
  const edges: FleetEdge[] = []
  for (const run of runs) {
    const parentId = run.parentAgentId
    const subtasks = run.subtasks ?? []
    if (!parentId || !agentIds.has(parentId) || subtasks.length === 0) continue
    const active = isActiveSwarmStatus(run.status)
    for (const sub of subtasks) {
      const childId = String(sub.agentId ?? "")
      if (!childId || !agentIds.has(childId) || childId === parentId) continue
      edges.push({
        id: `swarm-${run.id}-${parentId}-${childId}`,
        source: parentId,
        target: childId,
        kind: "delegates_to",
        label: "swarm",
        active,
      })
    }
  }
  return edges
}

export function buildFleetGraphModel(
  agents: FleetAgent[],
  swarmRuns: AgentSwarmRun[] = [],
): {
  edges: FleetEdge[]
  extraNodes: FleetGraphExtraNode[]
  activeAgentIds: Set<string>
  hasLiveSwarm: boolean
} {
  const agentIds = new Set(agents.map((a) => a.id))
  const connectors = buildConnectorEdges(agents)
  const parents = buildParentEdges(agents)
  const swarm = buildSwarmEdges(swarmRuns, agentIds)

  const activeAgentIds = new Set<string>()
  for (const edge of swarm) {
    if (!edge.active) continue
    activeAgentIds.add(edge.source)
    activeAgentIds.add(edge.target)
  }

  // Dedupe by id (swarm may overlap parent structural edges).
  const byId = new Map<string, FleetEdge>()
  for (const edge of [...parents, ...swarm, ...connectors.edges]) {
    const prev = byId.get(edge.id)
    if (!prev || (edge.active && !prev.active)) byId.set(edge.id, edge)
  }

  return {
    edges: [...byId.values()],
    extraNodes: connectors.nodes,
    activeAgentIds,
    hasLiveSwarm: activeAgentIds.size > 0,
  }
}

/** Simple layered layout: agents by department rows; connectors to the right. */
export function layoutFleetGraph(
  agents: FleetAgent[],
  extraNodes: FleetGraphExtraNode[],
): Record<string, { x: number; y: number }> {
  const positions: Record<string, { x: number; y: number }> = {}
  const colWidth = 220
  const rowHeight = 110
  const agentWidth = 188

  const byDept = new Map<string, FleetAgent[]>()
  for (const agent of agents) {
    const key = agent.departmentLabel || agent.department
    const list = byDept.get(key) ?? []
    list.push(agent)
    byDept.set(key, list)
  }

  let row = 0
  for (const [, rows] of byDept) {
    rows.forEach((agent, col) => {
      positions[agent.id] = {
        x: 24 + (col % 4) * colWidth,
        y: 24 + (row + Math.floor(col / 4)) * rowHeight,
      }
    })
    row += Math.max(1, Math.ceil(rows.length / 4))
  }

  const agentBottom =
    Object.values(positions).reduce((max, p) => Math.max(max, p.y), 24) + rowHeight

  extraNodes.forEach((node, i) => {
    positions[node.id] = {
      x: 24 + (i % 3) * colWidth + agentWidth + 40,
      y: agentBottom + Math.floor(i / 3) * 72,
    }
  })

  // If only connectors and few agents, place connectors to the right of agents.
  if (agents.length > 0 && extraNodes.length > 0) {
    const maxAgentX = Math.max(...agents.map((a) => positions[a.id]?.x ?? 0))
    extraNodes.forEach((node, i) => {
      positions[node.id] = {
        x: maxAgentX + colWidth + 48,
        y: 40 + i * 72,
      }
    })
  }

  return positions
}
