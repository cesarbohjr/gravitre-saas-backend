/**
 * The count on Knowledge's "Entities · N" control: every distinct entity the
 * graph can show, i.e. organization knowledge nodes plus each end of an active
 * learned relationship (test data excluded, as the graph hides it by default).
 */
import { entityKey, isSmokeTestEntityId, relationshipTouchesSmoke } from "@/lib/relationships-graph/utils"
import type { RelationshipRow } from "@/lib/relationships-graph/types"

export function countKnownEntities(nodes: RelationshipRow[], relationships: RelationshipRow[]): number {
  const keys = new Set<string>()
  const nodeIds = new Set<string>()
  for (const node of nodes) {
    const id = String(node.id ?? "").trim()
    if (id && !isSmokeTestEntityId(id)) {
      nodeIds.add(id)
      keys.add(`seed::${id}`)
    }
  }
  const add = (type: unknown, id: unknown) => {
    const raw = String(id ?? "").trim()
    if (!raw) return
    keys.add(nodeIds.has(raw) ? `seed::${raw}` : entityKey(type, raw))
  }
  for (const rel of relationships) {
    if (rel.archived_at || relationshipTouchesSmoke(rel)) continue
    add(rel.source_entity_type, rel.source_entity_id)
    add(rel.target_entity_type, rel.target_entity_id)
  }
  return keys.size
}
