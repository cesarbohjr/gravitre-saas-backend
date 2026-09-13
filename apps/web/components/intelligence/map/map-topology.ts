import type { IntelligenceCoreDepartment, IntelligenceCoreVisualState } from "@/lib/api"
import type { Agent } from "@/types/api"
import type { IntelligenceMapLens } from "./intelligence-map-lens"
import { formatDepartmentLabel, radialLayout } from "@/components/intelligence/core/types"
import { readString } from "@/lib/intelligence/helpers"

export type MapNodeKind = "department" | "agent" | "entity-type" | "model" | "signal"

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

export type MapEdge = {
  id: string
  fromId: string
  toId: string
  state: IntelligenceCoreVisualState
  opacity: number
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
        label: key,
        sublabel: readString(info?.status, "tracked"),
        state: readString(info?.status, "") === "ready" ? "resolved" : "low-confidence",
        emphasis: readString(info?.status, "") === "ready" ? 1 : 0.55,
      }))
      if (modelNodes.length === 0 && orgTraining) {
        for (const [key, row] of Object.entries(orgTraining).slice(0, 8)) {
          modelNodes.push({
            id: `model:${key}`,
            kind: "model",
            label: key,
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

/** Assign x/y in viewBox space for each node id. */
export function layoutMapNodes(
  nodes: MapNode[],
  center: { cx: number; cy: number },
  lens: IntelligenceMapLens,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const agents = nodes.filter((n) => n.kind === "agent")
  const entities = nodes.filter((n) => n.kind === "entity-type")
  const models = nodes.filter((n) => n.kind === "model")
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
