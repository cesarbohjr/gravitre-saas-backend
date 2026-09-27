import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import type { MapNode } from "@/components/intelligence/map/map-topology"

type GraphNodeLike = { id?: unknown; businessLabel?: unknown; type?: unknown }
type GraphEdgeLike = { id?: unknown; type?: unknown; fromId?: unknown; toId?: unknown }

export type SelectionRelation = {
  edgeId: string
  verb: string
  otherId: string
  otherLabel: string
  direction: "out" | "in"
}

const OUTGOING_VERB: Record<string, string> = {
  KNOWS: "Knows",
  RELATED_TO: "Related to",
  LEARNED_FROM: "Learned from",
  EVIDENCE_FOR: "Evidence for",
  PREDICTS: "Predicts",
  AFFECTS: "Affects",
  USED_BY: "Used by",
  ASSIGNED_TO: "Assigned to",
  EXECUTED: "Executed",
  READ_FROM: "Reads from",
  WROTE_TO: "Writes to",
  REQUIRES_APPROVAL: "Requires approval from",
  PRODUCED: "Produced",
  CONTRIBUTED_TO: "Contributed to",
  IMPROVED: "Improved",
  CONTRADICTS: "Contradicts",
}

const INCOMING_VERB: Record<string, string> = {
  KNOWS: "Known by",
  RELATED_TO: "Related to",
  LEARNED_FROM: "Taught",
  EVIDENCE_FOR: "Supported by",
  PREDICTS: "Predicted by",
  AFFECTS: "Affected by",
  USED_BY: "Uses",
  ASSIGNED_TO: "Assigned",
  EXECUTED: "Executed by",
  READ_FROM: "Read by",
  WROTE_TO: "Written by",
  REQUIRES_APPROVAL: "Approves",
  PRODUCED: "Produced by",
  CONTRIBUTED_TO: "Supported by",
  IMPROVED: "Improved by",
  CONTRADICTS: "Contradicted by",
}

/** Candidate canonical graph ids for a map selection (map ids drop the canonical prefix for some kinds). */
export function graphNodeIdsForSelection(selection: IntelligenceMapSelection): string[] {
  if (!selection) return []
  switch (selection.kind) {
    case "agent":
      return [`agent:${selection.agent.id}`, selection.agent.id]
    case "department":
      return [`dept:${selection.department.id}`, selection.department.id]
    case "signal": {
      const id = String(selection.signal.id ?? "")
      return id ? [`prediction:${id}`, id] : []
    }
    case "satellite":
      return [selection.node.id]
    default:
      return []
  }
}

/** Relationships recorded on the canonical graph for the selected node — nothing inferred. */
export function relationsForSelection(
  selection: IntelligenceMapSelection,
  graph: { nodes?: GraphNodeLike[]; edges?: GraphEdgeLike[] } | null | undefined,
): SelectionRelation[] {
  if (!selection || !graph?.edges?.length) return []
  const labels = new Map<string, string>()
  for (const node of graph.nodes ?? []) {
    if (typeof node.id === "string") {
      labels.set(node.id, typeof node.businessLabel === "string" && node.businessLabel ? node.businessLabel : node.id)
    }
  }

  if (selection.kind === "edge") {
    const edge = graph.edges.find((e) => e.id === selection.edgeId)
    if (!edge || typeof edge.fromId !== "string" || typeof edge.toId !== "string") return []
    const type = String(edge.type ?? "").toUpperCase()
    return [
      {
        edgeId: String(edge.id),
        verb: OUTGOING_VERB[type] ?? "Related to",
        otherId: edge.toId,
        otherLabel: `${labels.get(edge.fromId) ?? edge.fromId} → ${labels.get(edge.toId) ?? edge.toId}`,
        direction: "out",
      },
    ]
  }

  const candidates = graphNodeIdsForSelection(selection)
  const selfId = candidates.find((id) => labels.has(id)) ?? candidates[0]
  if (!selfId) return []

  const relations: SelectionRelation[] = []
  for (const edge of graph.edges) {
    if (typeof edge.fromId !== "string" || typeof edge.toId !== "string") continue
    const type = String(edge.type ?? "").toUpperCase()
    if (edge.fromId === selfId && edge.toId !== selfId) {
      relations.push({
        edgeId: String(edge.id ?? `${edge.fromId}-${edge.toId}`),
        verb: OUTGOING_VERB[type] ?? "Related to",
        otherId: edge.toId,
        otherLabel: labels.get(edge.toId) ?? edge.toId,
        direction: "out",
      })
    } else if (edge.toId === selfId && edge.fromId !== selfId) {
      relations.push({
        edgeId: String(edge.id ?? `${edge.fromId}-${edge.toId}`),
        verb: INCOMING_VERB[type] ?? "Related to",
        otherId: edge.fromId,
        otherLabel: labels.get(edge.fromId) ?? edge.fromId,
        direction: "in",
      })
    }
  }
  return relations.filter((r) => !r.otherId.startsWith("core:"))
}

/** Same mapping the field uses when a node is clicked. */
export function selectionForMapNode(node: MapNode): IntelligenceMapSelection {
  if (node.kind === "department" && node.department) return { kind: "department", department: node.department }
  if (node.kind === "agent" && node.agent) return { kind: "agent", agent: node.agent }
  if (node.kind === "signal" && node.signal) return { kind: "signal", signal: node.signal }
  return { kind: "satellite", node }
}
