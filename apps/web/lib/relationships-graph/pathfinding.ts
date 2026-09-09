import { entityKey, relationshipEdgeId } from "./utils"
import type { RelationshipRow } from "./types"

export type GraphPathStep = {
  edgeId: string
  relationshipType: string
  fromKey: string
  toKey: string
}

/** Undirected BFS paths between two entities using loaded relationship rows (max hops). */
export function findRelationshipPaths(
  relationships: RelationshipRow[],
  sourceType: string,
  sourceId: string,
  targetType: string,
  targetId: string,
  maxHops = 3,
): GraphPathStep[][] {
  const start = entityKey(sourceType, sourceId)
  const goal = entityKey(targetType, targetId)
  if (start === goal) return []

  type Edge = { neighbor: string; step: GraphPathStep }
  const adjacency = new Map<string, Edge[]>()

  for (const rel of relationships) {
    if (rel.archived_at) continue
    const a = entityKey(rel.source_entity_type, rel.source_entity_id)
    const b = entityKey(rel.target_entity_type, rel.target_entity_id)
    if (!a || !b || a === "::" || b === "::") continue
    const edgeId = relationshipEdgeId(rel)
    const type = String(rel.relationship_type ?? "")
    const stepAB: GraphPathStep = { edgeId, relationshipType: type, fromKey: a, toKey: b }
    const stepBA: GraphPathStep = { edgeId, relationshipType: type, fromKey: b, toKey: a }
    adjacency.set(a, [...(adjacency.get(a) ?? []), { neighbor: b, step: stepAB }])
    adjacency.set(b, [...(adjacency.get(b) ?? []), { neighbor: a, step: stepBA }])
  }

  const queue: { key: string; path: GraphPathStep[] }[] = [{ key: start, path: [] }]
  const visited = new Set<string>([start])
  const results: GraphPathStep[][] = []

  while (queue.length > 0 && results.length < 5) {
    const { key, path } = queue.shift()!
    if (path.length >= maxHops) continue
    for (const { neighbor, step } of adjacency.get(key) ?? []) {
      if (visited.has(neighbor)) continue
      const nextPath = [...path, step]
      if (neighbor === goal) {
        results.push(nextPath)
        continue
      }
      visited.add(neighbor)
      queue.push({ key: neighbor, path: nextPath })
    }
  }

  return results
}
