import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  CORE_ID,
  layoutMapNodes,
  type MapEdge,
  type MapNode,
} from "@/components/intelligence/map/map-topology"
import {
  CLUSTER_THRESHOLD,
  DEFAULT_GRAPH_CENTER,
  type GraphCluster,
  type GraphLayoutResult,
  type GraphPoint,
} from "./types"

export type GraphLayoutInput = {
  nodes: MapNode[]
  edges: MapEdge[]
  lens: IntelligenceMapLens
  cacheKey?: string
  pinnedPositions?: Map<string, GraphPoint>
  collapsedClusterIds?: Set<string>
}

const CACHE_PREFIX = "gravitre:intelligence-graph-layout:"

function layoutCacheKey(key: string): string {
  return `${CACHE_PREFIX}${key}`
}

function readLayoutCache(key: string): Map<string, GraphPoint> | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(layoutCacheKey(key))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Record<string, GraphPoint>
    return new Map(Object.entries(parsed))
  } catch {
    return null
  }
}

function writeLayoutCache(key: string, positions: Map<string, GraphPoint>): void {
  if (typeof window === "undefined" || !key) return
  try {
    const obj: Record<string, GraphPoint> = {}
    positions.forEach((pos, id) => {
      obj[id] = pos
    })
    sessionStorage.setItem(layoutCacheKey(key), JSON.stringify(obj))
  } catch {
    /* quota or private mode */
  }
}

function buildKindClusters(nodes: MapNode[]): GraphCluster[] {
  if (nodes.length <= CLUSTER_THRESHOLD) return []
  const byKind = new Map<string, MapNode[]>()
  for (const node of nodes) {
    const bucket = byKind.get(node.kind) ?? []
    bucket.push(node)
    byKind.set(node.kind, bucket)
  }
  return [...byKind.entries()]
    .filter(([, members]) => members.length >= 3)
    .map(([kind, members]) => ({
      id: `cluster:${kind}`,
      label: `${kind.replace("-", " ")} (${members.length})`,
      nodeIds: members.map((n) => n.id),
      collapsed: false,
      kind,
    }))
}

function centroid(points: GraphPoint[]): GraphPoint {
  if (points.length === 0) return DEFAULT_GRAPH_CENTER
  const sum = points.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }),
    { x: 0, y: 0 },
  )
  return { x: sum.x / points.length, y: sum.y / points.length }
}

/**
 * I2 — layout positions, clustering, collision refinement, pin + cache.
 */
export class GraphLayoutEngine {
  computeLayout(input: GraphLayoutInput): GraphLayoutResult {
    const { nodes, edges, lens, cacheKey, pinnedPositions, collapsedClusterIds } = input
    const clusters = buildKindClusters(nodes)
    const collapsed = collapsedClusterIds ?? new Set<string>()

    const hiddenNodeIds = new Set<string>()
    for (const cluster of clusters) {
      if (collapsed.has(cluster.id)) {
        cluster.collapsed = true
        cluster.nodeIds.forEach((id) => hiddenNodeIds.add(id))
      }
    }

    const visibleNodes = nodes.filter((node) => !hiddenNodeIds.has(node.id))
    let positions = layoutMapNodes(visibleNodes, DEFAULT_GRAPH_CENTER, lens, edges)

    if (cacheKey) {
      const cached = readLayoutCache(cacheKey)
      if (cached) {
        for (const [id, pos] of cached) {
          if (positions.has(id)) positions.set(id, pos)
        }
      }
    }

    if (pinnedPositions) {
      for (const [id, pos] of pinnedPositions) {
        if (positions.has(id)) positions.set(id, { ...pos })
      }
    }

    for (const cluster of clusters) {
      if (!cluster.collapsed) continue
      const memberPositions = cluster.nodeIds
        .map((id) => positions.get(id))
        .filter((p): p is GraphPoint => p != null)
      const center = centroid(memberPositions)
      positions.set(cluster.id, center)
    }

    positions.set(CORE_ID, { x: DEFAULT_GRAPH_CENTER.cx, y: DEFAULT_GRAPH_CENTER.cy })

    if (cacheKey) {
      writeLayoutCache(cacheKey, positions)
    }

    return {
      positions,
      clusters,
      coreId: CORE_ID,
    }
  }

  applyDraggedPosition(
    positions: Map<string, GraphPoint>,
    nodeId: string,
    point: GraphPoint,
    cacheKey?: string,
  ): Map<string, GraphPoint> {
    const next = new Map(positions)
    next.set(nodeId, point)
    if (cacheKey) writeLayoutCache(cacheKey, next)
    return next
  }

  fitBounds(
    positions: Map<string, GraphPoint>,
    nodeIds: string[],
    padding = 80,
  ): { minX: number; minY: number; maxX: number; maxY: number } | null {
    const points = nodeIds
      .map((id) => positions.get(id))
      .filter((p): p is GraphPoint => p != null)
    if (points.length === 0) return null
    points.push({ x: DEFAULT_GRAPH_CENTER.cx, y: DEFAULT_GRAPH_CENTER.cy })
    let minX = points[0]!.x
    let maxX = points[0]!.x
    let minY = points[0]!.y
    let maxY = points[0]!.y
    for (const p of points) {
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minY = Math.min(minY, p.y)
      maxY = Math.max(maxY, p.y)
    }
    return { minX: minX - padding, minY: minY - padding, maxX: maxX + padding, maxY: maxY + padding }
  }
}
