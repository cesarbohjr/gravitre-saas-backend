import {
  entityTypeLabel,
  relationshipTypeLabel,
} from "@/lib/learning-ui-copy"
import type { GraphNodeData, KnowledgeNodeRow, RelationshipRow, SortKey } from "./types"

export function entityKey(entityType: unknown, entityId: unknown): string {
  return `${String(entityType ?? "").trim()}::${String(entityId ?? "").trim()}`
}

export function seededNodeKey(nodeId: string): string {
  return `seed::${nodeId}`
}

export function confidenceTone(value: number): string {
  if (value >= 0.75) return "border-emerald-300 text-emerald-700 dark:text-emerald-300"
  if (value >= 0.5) return "border-amber-300 text-amber-700 dark:text-amber-300"
  return "border-rose-300 text-rose-700 dark:text-rose-300"
}

export function confidenceLabel(value: number): string {
  if (value >= 0.75) return "Strong"
  if (value >= 0.5) return "Moderate"
  return "Weak"
}

export function readNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function isSmokeTestEntityId(entityId: unknown): boolean {
  const id = String(entityId ?? "").trim().toLowerCase()
  return id.startsWith("smoke-") || id.includes("smoke-churn") || id.includes("smoke_")
}

export function relationshipTouchesSmoke(rel: RelationshipRow): boolean {
  return (
    isSmokeTestEntityId(rel.source_entity_id) || isSmokeTestEntityId(rel.target_entity_id)
  )
}

export function truncateEntityId(entityId: unknown, max = 10): string {
  const id = String(entityId ?? "").trim()
  if (id.length <= max) return id
  return `${id.slice(0, max)}…`
}

export function buildEntityLabelMap(relationships: RelationshipRow[]): Map<string, string> {
  const map = new Map<string, string>()
  for (const rel of relationships) {
    const sk = entityKey(rel.source_entity_type, rel.source_entity_id)
    const tk = entityKey(rel.target_entity_type, rel.target_entity_id)
    const sl = rel.source_label ?? rel.sourceLabel
    const tl = rel.target_label ?? rel.targetLabel
    if (sl) map.set(sk, String(sl))
    if (tl) map.set(tk, String(tl))
  }
  return map
}

export function makeLabelFor(
  glossaryById: Record<string, string>,
  entityLabelMap?: Map<string, string>,
  knowledgeNodeNames?: Record<string, string>,
) {
  return function labelFor(entityType: unknown, entityId: unknown): string {
    const type = String(entityType ?? "")
    const id = String(entityId ?? "")
    const key = entityKey(type, id)

    if (entityLabelMap?.has(key)) return entityLabelMap.get(key)!
    if (knowledgeNodeNames?.[id]) return knowledgeNodeNames[id]
    if (type === "glossary_term") {
      return glossaryById[id] ?? id
    }
    if (isSmokeTestEntityId(id)) {
      const suffix = id.split("-").pop() ?? id.slice(-4)
      return `Smoke test ${entityTypeLabel(type)} (${suffix})`
    }
    if (/^[0-9a-f-]{32,36}$/i.test(id)) {
      return `${entityTypeLabel(type)} (${truncateEntityId(id, 8)})`
    }
    return id
  }
}

export function filterAndSortRelationships(
  relationships: RelationshipRow[],
  options: {
    query: string
    typeFilter: string
    sortKey: SortKey
    labelFor: (entityType: unknown, entityId: unknown) => string
    showTestData?: boolean
    perspective?: string
  },
): RelationshipRow[] {
  const q = options.query.trim().toLowerCase()
  let rows = relationships.filter((rel) => {
    if (!options.showTestData && relationshipTouchesSmoke(rel)) return false
    if (options.perspective && options.perspective !== "all") {
      const p = options.perspective
      const st = String(rel.source_entity_type ?? "").toLowerCase()
      const tt = String(rel.target_entity_type ?? "").toLowerCase()
      if (p === "agents" && st !== "agent" && tt !== "agent") return false
      if (p === "customers" && st !== "customer" && tt !== "customer") return false
      if (p === "knowledge" && st !== "glossary_term" && tt !== "glossary_term") return false
      if (p === "organization") {
        const orgTypes = new Set(["company", "employee", "department", "vendor", "product"])
        if (!orgTypes.has(st) && !orgTypes.has(tt)) return false
      }
    }
    if (options.typeFilter !== "all" && String(rel.relationship_type ?? "") !== options.typeFilter) {
      return false
    }
    if (!q) return true
    const hay = [
      options.labelFor(rel.source_entity_type, rel.source_entity_id),
      options.labelFor(rel.target_entity_type, rel.target_entity_id),
      String(rel.relationship_type ?? ""),
      String(rel.source_entity_type ?? ""),
      String(rel.target_entity_type ?? ""),
    ]
      .join(" ")
      .toLowerCase()
    return hay.includes(q)
  })

  rows = [...rows].sort((a, b) => {
    if (options.sortKey === "confidence") {
      return readNumber(b.confidence) - readNumber(a.confidence)
    }
    if (options.sortKey === "evidence") {
      return readNumber(b.evidence_count) - readNumber(a.evidence_count)
    }
    const at = new Date(String(a.last_observed_at ?? a.created_at ?? 0)).getTime()
    const bt = new Date(String(b.last_observed_at ?? b.created_at ?? 0)).getTime()
    return (Number.isFinite(bt) ? bt : 0) - (Number.isFinite(at) ? at : 0)
  })

  return rows
}

export function collectRelationshipTypes(relationships: RelationshipRow[]): string[] {
  const set = new Set<string>()
  for (const rel of relationships) {
    const t = String(rel.relationship_type ?? "").trim()
    if (t) set.add(t)
  }
  return [...set].sort()
}

export function countNeedsReview(relationships: RelationshipRow[]): number {
  return relationships.filter((rel) => {
    if (rel.archived_at) return false
    const confidence = readNumber(rel.confidence)
    const evidence = readNumber(rel.evidence_count)
    return confidence < 0.5 || evidence < 2
  }).length
}

export function countNewThisWeek(relationships: RelationshipRow[]): number {
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000
  return relationships.filter((rel) => {
    const ts = new Date(String(rel.created_at ?? rel.last_observed_at ?? 0)).getTime()
    return Number.isFinite(ts) && ts >= weekAgo && !rel.archived_at
  }).length
}

export function buildGraphNodeData(
  entityType: string,
  entityId: string,
  label: string,
  isSeeded: boolean,
  knowledgeNodeId?: string,
): GraphNodeData {
  const showSecondary = label.trim() !== entityId.trim() && entityId.length > 0
  return {
    label,
    entityType,
    entityId,
    entityTypeLabel: entityTypeLabel(entityType),
    isSeeded,
    knowledgeNodeId,
    secondaryId: showSecondary ? entityId : undefined,
  }
}

export function knowledgeNodeLabel(node: KnowledgeNodeRow): string {
  return String(node.name ?? node.id ?? "")
}

export function relationshipEdgeId(rel: RelationshipRow): string {
  const id = String(rel.id ?? "").trim()
  if (id) return id
  return [
    rel.source_entity_type,
    rel.source_entity_id,
    rel.relationship_type,
    rel.target_entity_type,
    rel.target_entity_id,
  ]
    .map((v) => String(v ?? ""))
    .join("|")
}

export function relationshipTypeDisplay(value: unknown): string {
  return relationshipTypeLabel(String(value ?? ""))
}
