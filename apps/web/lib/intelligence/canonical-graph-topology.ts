import type { IntelligenceCoreVisualState } from "@/lib/api"
import type { Agent } from "@/types/api"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  CORE_ID,
  type MapEdge,
  type MapNode,
  type MapTopology,
} from "@/components/intelligence/map/map-topology"

export type CanonicalGraphNode = {
  id: string
  type: string
  businessLabel: string
  technicalLabel?: string | null
  status?: string | null
  metadata?: Record<string, unknown>
}

export type CanonicalGraphEdge = {
  id: string
  type: string
  fromId: string
  toId: string
}

const CANONICAL_CORE_ID = "core:gravitre"

const LENS_CAPTIONS: Record<IntelligenceMapLens, string> = {
  knows: "Knowledge — entities and domains from canonical intelligence graph",
  learns: "Learning — business insights from canonical intelligence graph",
  predicts: "Predictions — deduped signals from canonical intelligence graph",
  acts: "Actions — configured and running agents from canonical intelligence graph",
  improves: "Outcomes — measured improvements from canonical intelligence graph",
}

function mapVisualState(status: string | null | undefined): IntelligenceCoreVisualState {
  const normalized = (status ?? "").toLowerCase()
  if (normalized.includes("running") || normalized === "processing" || normalized === "trace") {
    return "trace"
  }
  if (normalized.includes("flow") || normalized === "active") return "flow-inward"
  if (normalized.includes("resolved") || normalized === "learned") return "resolved"
  if (normalized.includes("pending") || normalized.includes("approval")) return "pending-approval"
  if (normalized.includes("low") || normalized === "idle") return "idle"
  return "idle"
}

function agentForNode(node: CanonicalGraphNode, agents: Agent[] | null | undefined): Agent | undefined {
  const match = agents?.find((a) => `agent:${a.id}` === node.id || a.id === node.id.replace(/^agent:/, ""))
  if (match) return match
  const meta = node.metadata ?? {}
  return {
    id: node.id.replace(/^agent:/, ""),
    name: node.businessLabel,
    role: "Agent",
    department: "General",
    description: "",
    status: meta.isCurrentlyRunning ? "processing" : "active",
    personality: {
      color: "#6366f1",
      gradient: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
      glow: "rgba(99, 102, 241, 0.35)",
    },
    stats: { tasksToday: 0, successRate: null, avgResponseTime: "—", workflowsUsing: 0 },
    capabilities: [],
    permissions: [],
    lastAction: String(meta.executionStatus ?? node.status ?? ""),
    lastActionTime: "",
  }
}

export function resolveCanonicalGraphMapNode(
  nodeId: string,
  graph: { nodes: CanonicalGraphNode[] } | null | undefined,
  agents?: Agent[] | null,
): MapNode | null {
  const node = graph?.nodes?.find((entry) => entry.id === nodeId)
  if (!node) return null
  return nodeToMapNode(node, agents)
}

function nodeToMapNode(node: CanonicalGraphNode, agents: Agent[] | null | undefined): MapNode | null {
  if (node.type === "core") return null
  const state = mapVisualState(node.status)
  const emphasis =
    node.metadata?.isConfiguredActive === false && node.type === "agent" ? 0.4 : 1

  switch (node.type) {
    case "domain":
      return {
        id: node.id,
        kind: "department",
        label: node.businessLabel,
        sublabel: node.status ?? undefined,
        state,
        department: {
          id: node.id.replace(/^dept:/, ""),
          eventsInWindow: Number(node.metadata?.eventsInWindow ?? 0),
          recentInflow: 0,
          recentResolved: Number(node.metadata?.recentResolved ?? 0),
          confidence: null,
          state,
        },
        emphasis,
      }
    case "agent": {
      const agent = agentForNode(node, agents)
      return {
        id: node.id,
        kind: "agent",
        label: node.businessLabel,
        sublabel: node.metadata?.isCurrentlyRunning ? "running" : String(node.status ?? ""),
        state,
        agent,
        emphasis: node.metadata?.isCurrentlyRunning ? 1 : emphasis,
      }
    }
    case "prediction":
      return {
        id: node.id,
        kind: "signal",
        label: node.businessLabel,
        sublabel: node.metadata?.confidence != null ? `${Math.round(Number(node.metadata.confidence) * 100)}% confidence` : "Prediction",
        state: "pending-approval",
        signal: {
          id: node.id.replace(/^prediction:/, ""),
          title: node.businessLabel,
          department: node.metadata?.department,
          confidence: node.metadata?.confidence,
        },
        emphasis: 1,
      }
    case "learning":
      return {
        id: node.id,
        kind: "learning",
        label: node.businessLabel,
        sublabel: "Business learning",
        state: "resolved",
        emphasis: 1,
      }
    case "model":
      return {
        id: node.id,
        kind: "model",
        label: node.businessLabel,
        sublabel: node.status ?? undefined,
        state,
        emphasis: node.status === "ready" ? 1 : 0.55,
      }
    case "entity":
    case "knowledge":
      return {
        id: node.id,
        kind: "entity-type",
        label: node.businessLabel,
        sublabel: node.type,
        state: "flow-inward",
        emphasis: 1,
      }
    case "outcome":
      return {
        id: node.id,
        kind: "department",
        label: node.businessLabel,
        sublabel: "Outcome",
        state: "resolved",
        emphasis: 1,
      }
    default:
      return {
        id: node.id,
        kind: "entity-type",
        label: node.businessLabel,
        sublabel: node.type,
        state,
        emphasis: 0.7,
      }
  }
}

function remapCoreId(id: string): string {
  return id === CANONICAL_CORE_ID ? CORE_ID : id
}

/** G3 — Project canonical IntelligenceGraph into map topology (same graph, lens-filtered). */
export function buildTopologyFromCanonicalGraph({
  graph,
  lens,
  agents,
}: {
  graph: { nodes: CanonicalGraphNode[]; edges: CanonicalGraphEdge[] }
  lens: IntelligenceMapLens
  agents?: Agent[] | null
}): MapTopology {
  const nodes = graph.nodes
    .map((node) => nodeToMapNode(node, agents))
    .filter((node): node is MapNode => node != null)

  const nodeIds = new Set(nodes.map((n) => n.id))
  const edges: MapEdge[] = graph.edges
    .map((edge) => {
      const fromId = remapCoreId(edge.fromId)
      const toId = remapCoreId(edge.toId)
      if (fromId !== CORE_ID && !nodeIds.has(fromId)) return null
      if (toId !== CORE_ID && !nodeIds.has(toId)) return null
      return {
        id: edge.id,
        fromId,
        toId,
        state: mapVisualState(edge.type.toLowerCase()),
        opacity: edge.type === "CONTRADICTS" ? 0.35 : 0.65,
      }
    })
    .filter((edge): edge is MapEdge => edge != null)

  return {
    nodes,
    edges,
    caption:
      nodes.length > 0
        ? LENS_CAPTIONS[lens]
        : `${LENS_CAPTIONS[lens]} — no nodes in this lens yet`,
  }
}
