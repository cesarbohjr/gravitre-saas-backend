import { entityKey } from "./utils"
import type { RelationshipRow } from "./types"

export type EntityMatchCandidate = {
  id: string
  name: string
  nodeType?: string
  entityType: string
  entityId: string
  matchScore: number
  source: "confirmed_knowledge" | "learned_relationship"
  evidenceCount?: number
}

function scoreNameMatch(candidate: string, target: string): number {
  const cand = candidate.trim().toLowerCase()
  const node = target.trim().toLowerCase()
  if (!cand || !node) return 0
  if (cand === node) return 100
  if (node.startsWith(cand) || cand.startsWith(node)) return 80
  if (cand.includes(node) || node.includes(cand)) return 60
  return 0
}

/** Client-side learned-entity name matches from loaded relationship labels. */
export function findLearnedEntityMatches(
  name: string,
  relationships: RelationshipRow[],
  labelFor: (entityType: unknown, entityId: unknown) => string,
  minScore = 60,
  limit = 5,
): EntityMatchCandidate[] {
  const query = name.trim()
  if (!query) return []

  const seen = new Map<string, EntityMatchCandidate>()

  for (const rel of relationships) {
    if (rel.archived_at) continue
    for (const [entityType, entityId] of [
      [rel.source_entity_type, rel.source_entity_id],
      [rel.target_entity_type, rel.target_entity_id],
    ] as const) {
      const type = String(entityType ?? "")
      const id = String(entityId ?? "")
      if (!type || !id) continue
      const key = entityKey(type, id)
      if (seen.has(key)) continue
      const label = labelFor(type, id)
      const score = scoreNameMatch(query, label)
      if (score < minScore) continue
      seen.set(key, {
        id: key,
        name: label,
        entityType: type,
        entityId: id,
        matchScore: score,
        source: "learned_relationship",
        evidenceCount: Number(rel.evidence_count ?? 0) || undefined,
      })
    }
  }

  return [...seen.values()]
    .sort((a, b) => b.matchScore - a.matchScore || a.name.localeCompare(b.name))
    .slice(0, limit)
}
