/**
 * I9 — Focused relationship paths for mobile (not a shrunk 40-node canvas).
 */
import { CORE_ID, type MapNode, type MapTopology } from "@/components/intelligence/map/map-topology"

export type FocusedRelationshipPath = {
  id: string
  fromLabel: string
  toLabel: string
  edgeType: string
}

export function focusedRelationshipPaths(
  topology: MapTopology | null | undefined,
  max = 8,
): FocusedRelationshipPath[] {
  if (!topology?.edges?.length) return []
  const byId = new Map(topology.nodes.map((node) => [node.id, node]))
  const paths: FocusedRelationshipPath[] = []
  for (const edge of topology.edges) {
    if (paths.length >= max) break
    const from = labelFor(byId.get(edge.fromId), edge.fromId)
    const to = labelFor(byId.get(edge.toId), edge.toId)
    if (!from || !to) continue
    paths.push({
      id: edge.id,
      fromLabel: from,
      toLabel: to,
      edgeType: (edge.edgeType ?? "RELATED_TO").replace(/_/g, " ").toLowerCase(),
    })
  }
  return paths
}

function labelFor(node: MapNode | undefined, id: string): string | null {
  if (id === CORE_ID || id === "__core__") return "Gravitre Intelligence"
  if (!node) return null
  return node.label
}

export function isCompactIntelligenceViewport(): boolean {
  if (typeof window === "undefined") return false
  return window.matchMedia("(max-width: 767px)").matches
}
