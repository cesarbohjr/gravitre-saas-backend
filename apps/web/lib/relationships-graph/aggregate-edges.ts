import type { Edge, Node } from "@xyflow/react"
import { entityKey, readNumber, relationshipEdgeId, relationshipTypeDisplay } from "./utils"
import type { GraphEdgeData, GraphNodeData, RelationshipRow } from "./types"

export const CLUSTER_PREFIX = "cluster::"
export const AGGREGATE_MIN_COUNT = 3

export type AggregateCluster = {
  id: string
  relationshipType: string
  sourceEntityType: string
  targetKey: string
  memberKeys: string[]
  relationships: RelationshipRow[]
}

/** Group parallel edges (e.g. many customers tracked-by one agent). */
export function detectAggregateClusters(relationships: RelationshipRow[]): AggregateCluster[] {
  const buckets = new Map<string, RelationshipRow[]>()

  for (const rel of relationships) {
    if (rel.archived_at) continue
    const relType = String(rel.relationship_type ?? "")
    const sourceType = String(rel.source_entity_type ?? "")
    const targetType = String(rel.target_entity_type ?? "")
    const targetId = String(rel.target_entity_id ?? "")
    if (!relType || !sourceType || !targetId) continue

    const targetKey = entityKey(targetType, targetId)
    const bucketKey = `${relType}|${sourceType}|${targetKey}`
    const list = buckets.get(bucketKey) ?? []
    list.push(rel)
    buckets.set(bucketKey, list)
  }

  const clusters: AggregateCluster[] = []
  for (const [bucketKey, rels] of buckets) {
    const uniqueSources = new Set(
      rels.map((r) => entityKey(String(r.source_entity_type ?? ""), String(r.source_entity_id ?? ""))),
    )
    if (uniqueSources.size < AGGREGATE_MIN_COUNT) continue

    const [relationshipType, sourceEntityType, targetKey] = bucketKey.split("|")
    const id = `${CLUSTER_PREFIX}${bucketKey}`
    clusters.push({
      id,
      relationshipType,
      sourceEntityType,
      targetKey,
      memberKeys: [...uniqueSources],
      relationships: rels,
    })
  }

  return clusters
}

export function applyEdgeAggregation(
  nodes: Node<GraphNodeData>[],
  edges: Edge<GraphEdgeData>[],
  relationships: RelationshipRow[],
  expandedClusters: Set<string>,
  labelFor: (entityType: unknown, entityId: unknown) => string,
): { nodes: Node<GraphNodeData>[]; edges: Edge<GraphEdgeData>[] } {
  const clusters = detectAggregateClusters(relationships)
  if (clusters.length === 0) return { nodes, edges }

  const hiddenMemberKeys = new Set<string>()
  const clusterNodes: Node<GraphNodeData>[] = []
  const clusterEdges: Edge<GraphEdgeData>[] = []
  const suppressedEdgeIds = new Set<string>()

  for (const cluster of clusters) {
    const expanded = expandedClusters.has(cluster.id)
    if (expanded) continue

    for (const key of cluster.memberKeys) hiddenMemberKeys.add(key)
    for (const rel of cluster.relationships) suppressedEdgeIds.add(relationshipEdgeId(rel))

    const [targetType, targetId] = cluster.targetKey.split("::")
    const typeLabel = cluster.sourceEntityType.replace(/_/g, " ")
    const count = cluster.memberKeys.length
    clusterNodes.push({
      id: cluster.id,
      type: "relationshipEntity",
      position: { x: 0, y: 0 },
      data: {
        label: `${count} ${typeLabel}${count === 1 ? "" : "s"}`,
        entityType: cluster.sourceEntityType,
        entityId: cluster.id,
        entityTypeLabel: typeLabel,
        isSeeded: false,
        isCluster: true,
        clusterId: cluster.id,
        clusterCount: count,
        clusterExpanded: false,
      },
    })

    const sample = cluster.relationships[0]
    const avgConf =
      cluster.relationships.reduce((sum, r) => sum + readNumber(r.confidence), 0) /
      cluster.relationships.length
    const totalEvidence = cluster.relationships.reduce(
      (sum, r) => sum + readNumber(r.evidence_count),
      0,
    )

    clusterEdges.push({
      id: `agg-${cluster.id}->${cluster.targetKey}`,
      source: cluster.id,
      target: cluster.targetKey,
      label: `${relationshipTypeDisplay(cluster.relationshipType)} · ${count}`,
      data: {
        relationshipType: cluster.relationshipType,
        relationshipTypeLabel: relationshipTypeDisplay(cluster.relationshipType),
        confidence: avgConf,
        evidenceCount: totalEvidence,
        archived: false,
        relationshipId: cluster.id,
        raw: sample,
        isAggregate: true,
        aggregateCount: count,
        clusterId: cluster.id,
      },
      animated: avgConf >= 0.75,
    })
  }

  const visibleNodes = nodes.filter((n) => !hiddenMemberKeys.has(n.id)).concat(clusterNodes)
  const visibleEdges = edges
    .filter((e) => !suppressedEdgeIds.has(e.id))
    .concat(clusterEdges)

  return { nodes: visibleNodes, edges: visibleEdges }
}
