export type RelationshipRow = Record<string, unknown>
export type KnowledgeNodeRow = Record<string, unknown>

export type SortKey = "recent" | "confidence" | "evidence"

export type ViewMode = "graph" | "table"

export type Selection =
  | { kind: "node"; nodeId: string }
  | { kind: "edge"; edgeId: string }
  | null

export type GraphNodeData = {
  label: string
  entityType: string
  entityId: string
  entityTypeLabel: string
  isSeeded: boolean
  knowledgeNodeId?: string
  secondaryId?: string
  isCluster?: boolean
  clusterId?: string
  clusterCount?: number
  clusterExpanded?: boolean
}

export type GraphEdgeData = {
  relationshipType: string
  relationshipTypeLabel: string
  confidence: number
  evidenceCount: number
  archived: boolean
  relationshipId: string
  raw: RelationshipRow
  isAggregate?: boolean
  aggregateCount?: number
  clusterId?: string
}

export type AddNodeMode = "first" | "entity"
