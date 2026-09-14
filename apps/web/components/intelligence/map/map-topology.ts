import type { IntelligenceCoreDepartment, IntelligenceCoreVisualState } from "@/lib/api"
import type { Agent } from "@/types/api"
import type { IntelligenceMapLens } from "./intelligence-map-lens"
import { formatDepartmentLabel, radialLayout } from "@/components/intelligence/core/types"
import { readString } from "@/lib/intelligence/helpers"
import { modelBusinessLabel } from "@/lib/intelligence/business-labels"

export type MapNodeKind = "department" | "agent" | "entity-type" | "model" | "signal" | "learning"

export type MapNode = {
  id: string
  kind: MapNodeKind
  label: string
  sublabel?: string
  state?: IntelligenceCoreVisualState
  department?: IntelligenceCoreDepartment
  agent?: Agent
  signal?: Record<string, unknown>
  emphasis: number
}

export type MapEdgeType =
  | "KNOWS"
  | "RELATED_TO"
  | "LEARNED_FROM"
  | "EVIDENCE_FOR"
  | "PREDICTS"
  | "AFFECTS"
  | "USED_BY"
  | "ASSIGNED_TO"
  | "EXECUTED"
  | "READ_FROM"
  | "WROTE_TO"
  | "REQUIRES_APPROVAL"
  | "PRODUCED"
  | "CONTRIBUTED_TO"
  | "IMPROVED"
  | "CONTRADICTS"
  | "core"

export type MapEdge = {
  id: string
  fromId: string
  toId: string
  state: IntelligenceCoreVisualState
  opacity: number
  /** G3 — canonical IntelligenceEdgeType for semantic edge styling. */
  edgeType?: MapEdgeType
  /** Emphasis multiplier for highlighted edge types (G4 expandNodeIds / edgeTypes). */
  emphasis?: number
}

export type MapTopology = {
  nodes: MapNode[]
  edges: MapEdge[]
  caption: string
}

const CORE_ID = "__core__"

function normalizeDeptKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "_")
}

function agentDeptKey(agent: Agent): string {
  return normalizeDeptKey(agent.department ?? "general")
}

function signalDepartmentKey(signal: Record<string, unknown>): string | null {
  const raw = signal.department ?? signal.department_id ?? signal.departmentId ?? signal.domain
  if (typeof raw === "string" && raw.trim()) return normalizeDeptKey(raw)
  const title = readString(signal.title, "").toLowerCase()
  if (title.includes("hubspot") || title.includes("sales")) return "sales"
  if (title.includes("support") || title.includes("ticket")) return "support"
  if (title.includes("finance") || title.includes("billing")) return "finance"
  if (title.includes("marketing")) return "marketing"
  return null
}

function deptNode(dept: IntelligenceCoreDepartment, emphasis: number): MapNode {
  return {
    id: `dept:${dept.id}`,
    kind: "department",
    label: formatDepartmentLabel(dept.id),
    sublabel: dept.eventsInWindow > 0 ? `${dept.eventsInWindow} events` : undefined,
    state: dept.state,
    department: dept,
    emphasis,
  }
}

function coreEdges(nodes: MapNode[], state: IntelligenceCoreVisualState, opacity = 0.55): MapEdge[] {
  return nodes.map((node) => ({
    id: `edge:core:${node.id}`,
    fromId: CORE_ID,
    toId: node.id,
    state,
    opacity,
  }))
}

export function buildMapTopology({
  lens,
  departments,
  agents,
  entityTypes,
  readiness,
  orgTraining,
  signals,
  coreState,
}: {
  lens: IntelligenceMapLens
  departments: IntelligenceCoreDepartment[]
  agents: Agent[] | null | undefined
  entityTypes: string[] | null | undefined
  readiness: Record<string, unknown> | null | undefined
  orgTraining: Record<string, { artifact_loaded?: boolean }> | null | undefined
  signals: Record<string, unknown>[] | null | undefined
  coreState: IntelligenceCoreVisualState
}): MapTopology {
  switch (lens) {
    case "knows": {
      const types = (entityTypes ?? []).slice(0, 8)
      const entityNodes: MapNode[] = types.map((type) => ({
        id: `entity:${type}`,
        kind: "entity-type",
        label: type.replace(/_/g, " "),
        sublabel: "Entity type",
        state: "flow-inward",
        emphasis: 1,
      }))
      const deptNodes = departments.map((d) => deptNode(d, d.eventsInWindow > 0 ? 0.85 : 0.45))
      const nodes = [...entityNodes, ...deptNodes]
      const edges = [
        ...coreEdges(entityNodes, "flow-inward", 0.75),
        ...coreEdges(deptNodes, coreState, 0.5),
      ]
      return {
        nodes,
        edges,
        caption:
          types.length > 0
            ? "Knowledge lens — entity types and departments with live activity"
            : "Knowledge lens — no entity types in graph yet; showing live departments only",
      }
    }

    case "learns": {
      const byModel = (readiness?.by_model as Record<string, Record<string, unknown>> | undefined) ?? {}
      const modelEntries = Object.entries(byModel).slice(0, 8)
      const modelNodes: MapNode[] = modelEntries.map(([key, info]) => ({
        id: `model:${key}`,
        kind: "model",
        label: modelBusinessLabel(key),
        sublabel: readString(info?.status, "tracked"),
        state: readString(info?.status, "") === "ready" ? "resolved" : "low-confidence",
        emphasis: readString(info?.status, "") === "ready" ? 1 : 0.55,
      }))
      if (modelNodes.length === 0 && orgTraining) {
        for (const [key, row] of Object.entries(orgTraining).slice(0, 8)) {
          modelNodes.push({
            id: `model:${key}`,
            kind: "model",
            label: modelBusinessLabel(key),
            sublabel: row?.artifact_loaded ? "artifact loaded" : "not loaded",
            state: row?.artifact_loaded ? "trace" : "idle",
            emphasis: row?.artifact_loaded ? 1 : 0.4,
          })
        }
      }
      const nodes = modelNodes
      return {
        nodes,
        edges: coreEdges(modelNodes, "trace", 0.7),
        caption:
          modelNodes.length > 0
            ? "Learns lens — models tracked for training and improvement"
            : "Learns lens — no model training signals yet",
      }
    }

    case "predicts": {
      const signalList = (signals ?? []).slice(0, 6)
      const deptNodes = departments.map((d) => {
        const hasWarning = signalList.some((s) => signalDepartmentKey(s) === normalizeDeptKey(d.id))
        return deptNode(d, hasWarning ? 1 : d.confidence != null ? 0.75 : 0.4)
      })
      const orphanSignals = signalList.filter((s) => !signalDepartmentKey(s))
      const signalNodes: MapNode[] = orphanSignals.map((signal, i) => ({
        id: `signal:${readString(signal.id, String(i))}`,
        kind: "signal",
        label: readString(signal.title, "Signal"),
        sublabel: "Unscoped prediction",
        state: "pending-approval",
        signal,
        emphasis: 1,
      }))
      const nodes = [...deptNodes, ...signalNodes]
      const edges = [
        ...coreEdges(deptNodes, coreState, 0.55),
        ...coreEdges(signalNodes, "pending-approval", 0.85),
      ]
      return {
        nodes,
        edges,
        caption: "Predicts lens — warnings and confidence by department",
      }
    }

    case "acts": {
      const agentList = [...(agents ?? [])]
        .sort((a, b) => {
          const rank = (s: Agent["status"]) => (s === "processing" ? 0 : s === "active" ? 1 : 2)
          return rank(a.status) - rank(b.status)
        })
        .slice(0, 8)
      const agentNodes: MapNode[] = agentList.map((agent) => ({
        id: `agent:${agent.id}`,
        kind: "agent",
        label: agent.name,
        sublabel: agent.status,
        state: agent.status === "processing" ? "trace" : agent.status === "active" ? "flow-inward" : "idle",
        agent,
        emphasis: agent.status === "processing" || agent.status === "active" ? 1 : 0.45,
      }))
      const deptNodes = departments.map((d) => deptNode(d, d.state === "trace" ? 1 : 0.5))
      const nodes = [...agentNodes, ...deptNodes]
      const edges: MapEdge[] = [
        ...coreEdges(agentNodes, "trace", 0.8),
        ...coreEdges(deptNodes, coreState, 0.45),
      ]
      for (const agentNode of agentNodes) {
        const agent = agentNode.agent!
        const deptKey = agentDeptKey(agent)
        const target = deptNodes.find((n) => normalizeDeptKey(n.department!.id) === deptKey)
        if (target) {
          edges.push({
            id: `edge:${agentNode.id}:${target.id}`,
            fromId: agentNode.id,
            toId: target.id,
            state: agentNode.state ?? "trace",
            opacity: 0.65,
          })
        }
      }
      return {
        nodes,
        edges,
        caption:
          agentNodes.length > 0
            ? "Acts lens — agents executing and connected to departments"
            : "Acts lens — no agents in org; showing department activity only",
      }
    }

    case "improves": {
      const sorted = [...departments].sort((a, b) => b.recentResolved - a.recentResolved)
      const nodes = sorted.map((d) =>
        deptNode(d, d.recentResolved > 0 || d.state === "resolved" ? 1 : 0.35),
      )
      return {
        nodes,
        edges: coreEdges(
          nodes,
          nodes.some((n) => (n.department?.recentResolved ?? 0) > 0) ? "resolved" : coreState,
          0.6,
        ),
        caption: "Improves lens — outcomes resolving through departments",
      }
    }

    default:
      return { nodes: departments.map((d) => deptNode(d, 1)), edges: coreEdges(departments.map((d) => deptNode(d, 1)), coreState), caption: "" }
  }
}

/** G3 — Lightweight force-directed refinement (prefers-reduced-motion skips via caller). */
export function refineLayoutWithForces(
  positions: Map<string, { x: number; y: number }>,
  edges: MapEdge[],
  center: { cx: number; cy: number },
  iterations = 24,
): Map<string, { x: number; y: number }> {
  if (positions.size < 3) return positions
  const ids = [...positions.keys()]
  const next = new Map(positions)

  for (let step = 0; step < iterations; step += 1) {
    const displacement = new Map<string, { dx: number; dy: number }>()
    ids.forEach((id) => displacement.set(id, { dx: 0, dy: 0 }))

    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const idA = ids[i]!
        const idB = ids[j]!
        const a = next.get(idA)
        const b = next.get(idB)
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.max(Math.hypot(dx, dy), 12)
        const repulse = 4200 / (dist * dist)
        const fx = (dx / dist) * repulse
        const fy = (dy / dist) * repulse
        displacement.get(idA)!.dx -= fx
        displacement.get(idA)!.dy -= fy
        displacement.get(idB)!.dx += fx
        displacement.get(idB)!.dy += fy
      }
    }

    for (const edge of edges) {
      const fromId = edge.fromId === CORE_ID ? null : edge.fromId
      const toId = edge.toId === CORE_ID ? null : edge.toId
      if (!fromId || !toId) continue
      const from = next.get(fromId)
      const to = next.get(toId)
      if (!from || !to) continue
      const dx = to.x - from.x
      const dy = to.y - from.y
      const dist = Math.max(Math.hypot(dx, dy), 1)
      const pull = (dist - 95) * 0.04
      const fx = (dx / dist) * pull
      const fy = (dy / dist) * pull
      displacement.get(fromId)!.dx += fx
      displacement.get(fromId)!.dy += fy
      displacement.get(toId)!.dx -= fx
      displacement.get(toId)!.dy -= fy
    }

    const damp = 0.82 - step / (iterations * 4)
    ids.forEach((id) => {
      const pos = next.get(id)
      const delta = displacement.get(id)
      if (!pos || !delta) return
      pos.x += delta.dx * damp
      pos.y += delta.dy * damp
      pos.x += (center.cx - pos.x) * 0.002
      pos.y += (center.cy - pos.y) * 0.002
    })
  }

  return next
}

const KIND_RING_RADIUS: Partial<Record<MapNodeKind, number>> = {
  agent: 145,
  "entity-type": 130,
  model: 165,
  learning: 165,
  signal: 230,
  department: 200,
}

/** G3 — Semantic layout: group by node kind + edge connectivity, not one flat ring. */
export function layoutSemanticGraphNodes(
  nodes: MapNode[],
  center: { cx: number; cy: number },
  lens: IntelligenceMapLens,
  edges: MapEdge[],
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  if (nodes.length === 0) return positions

  const byKind = new Map<MapNodeKind, MapNode[]>()
  for (const node of nodes) {
    const bucket = byKind.get(node.kind) ?? []
    bucket.push(node)
    byKind.set(node.kind, bucket)
  }

  const neighborWeight = new Map<string, number>()
  for (const edge of edges) {
    if (edge.fromId === CORE_ID || edge.toId === CORE_ID) {
      const satelliteId = edge.fromId === CORE_ID ? edge.toId : edge.fromId
      neighborWeight.set(satelliteId, (neighborWeight.get(satelliteId) ?? 0) + 1)
    }
  }

  const sortByConnectivity = (ringNodes: MapNode[]) =>
    [...ringNodes].sort((a, b) => {
      const delta = (neighborWeight.get(b.id) ?? 0) - (neighborWeight.get(a.id) ?? 0)
      if (delta !== 0) return delta
      return a.label.localeCompare(b.label)
    })

  const placeKindRing = (kind: MapNodeKind, radius: number, phase = 0) => {
    const ringNodes = sortByConnectivity(byKind.get(kind) ?? [])
    if (ringNodes.length === 0) return
    const coords = radialLayout(ringNodes.length, { cx: center.cx, cy: center.cy, radius })
    ringNodes.forEach((node, i) => {
      const base = coords[i]
      if (!base) return
      const angle = Math.atan2(base.y - center.cy, base.x - center.cx) + phase
      positions.set(node.id, {
        x: center.cx + radius * Math.cos(angle),
        y: center.cy + radius * Math.sin(angle),
      })
    })
  }

  const finalize = () => refineLayoutWithForces(positions, edges, center)

  if (lens === "acts") {
    placeKindRing("agent", KIND_RING_RADIUS.agent ?? 145)
    placeKindRing("department", KIND_RING_RADIUS.department ?? 210, Math.PI / 16)
    for (const node of nodes) {
      if (!positions.has(node.id)) placeKindRing(node.kind, 195)
    }
    return finalize()
  }
  if (lens === "knows") {
    placeKindRing("entity-type", KIND_RING_RADIUS["entity-type"] ?? 130)
    placeKindRing("department", KIND_RING_RADIUS.department ?? 200, Math.PI / 12)
    for (const node of nodes) {
      if (!positions.has(node.id)) placeKindRing(node.kind, 195)
    }
    return finalize()
  }
  if (lens === "predicts") {
    placeKindRing("department", 175)
    placeKindRing("signal", KIND_RING_RADIUS.signal ?? 230, Math.PI / 10)
    for (const node of nodes) {
      if (!positions.has(node.id)) placeKindRing(node.kind, 195)
    }
    return finalize()
  }
  if (lens === "learns") {
    placeKindRing("learning", KIND_RING_RADIUS.learning ?? 165)
    placeKindRing("model", KIND_RING_RADIUS.model ?? 185, Math.PI / 8)
    for (const node of nodes) {
      if (!positions.has(node.id)) placeKindRing(node.kind, 195)
    }
    return finalize()
  }
  if (lens === "improves") {
    placeKindRing("department", KIND_RING_RADIUS.department ?? 200)
    for (const node of nodes) {
      if (!positions.has(node.id)) placeKindRing(node.kind, 195)
    }
    return finalize()
  }

  const coords = radialLayout(nodes.length, { cx: center.cx, cy: center.cy, radius: 195 })
  nodes.forEach((node, i) => {
    const pos = coords[i]
    if (pos) positions.set(node.id, pos)
  })
  return finalize()
}

/** Assign x/y in viewBox space for each node id. */
export function layoutMapNodes(
  nodes: MapNode[],
  center: { cx: number; cy: number },
  lens: IntelligenceMapLens,
  edges?: MapEdge[],
): Map<string, { x: number; y: number }> {
  if (edges && edges.length > 0 && nodes.length > 0) {
    return layoutSemanticGraphNodes(nodes, center, lens, edges)
  }

  const positions = new Map<string, { x: number; y: number }>()
  const agents = nodes.filter((n) => n.kind === "agent")
  const entities = nodes.filter((n) => n.kind === "entity-type")
  const signals = nodes.filter((n) => n.kind === "signal")
  const depts = nodes.filter((n) => n.kind === "department")

  const placeRing = (ringNodes: MapNode[], radius: number) => {
    const coords = radialLayout(ringNodes.length, { cx: center.cx, cy: center.cy, radius })
    ringNodes.forEach((node, i) => {
      const pos = coords[i]
      if (pos) positions.set(node.id, pos)
    })
  }

  if (lens === "acts" && agents.length > 0) {
    placeRing(agents, 145)
    placeRing(depts, 210)
    return positions
  }
  if (lens === "knows" && entities.length > 0) {
    placeRing(entities, 130)
    placeRing(depts, 200)
    return positions
  }
  if (lens === "predicts" && signals.length > 0) {
    placeRing(depts, 175)
    placeRing(signals, 230)
    return positions
  }
  placeRing(nodes, 195)
  return positions
}

export { CORE_ID, signalDepartmentKey, normalizeDeptKey }
