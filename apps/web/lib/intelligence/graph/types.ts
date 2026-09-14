import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import type { MapEdge, MapNode, MapTopology } from "@/components/intelligence/map/map-topology"

/** Mirror of backend IntelligenceGraphNode.type (intelligence_projection.py). */
export type IntelligenceGraphNodeType =
  | "core"
  | "domain"
  | "entity"
  | "knowledge"
  | "learning"
  | "prediction"
  | "model"
  | "agent"
  | "outcome"
  | "signal"
  | "objective"
  | "connector"
  | "evidence"
  | "action"

export type IntelligenceGraphEdgeType =
  | "KNOWS"
  | "RELATED_TO"
  | "LEARNED_FROM"
  | "EVIDENCE_FOR"
  | "PREDICTS"
  | "AFFECTS"
  | "USED_BY"
  | "ASSIGNED_TO"
  | "EXECUTED"
  | "READ_FROM"
  | "WROTE_TO"
  | "REQUIRES_APPROVAL"
  | "PRODUCED"
  | "CONTRIBUTED_TO"
  | "IMPROVED"
  | "CONTRADICTS"

export type GraphViewBox = { w: number; h: number }
export type GraphPoint = { x: number; y: number }
export type GraphCenter = { cx: number; cy: number }

export type GraphViewport = {
  scale: number
  translateX: number
  translateY: number
}

export type GraphCluster = {
  id: string
  label: string
  nodeIds: string[]
  collapsed: boolean
  kind: string
}

export type GraphLayoutResult = {
  positions: Map<string, GraphPoint>
  clusters: GraphCluster[]
  coreId: string
}

export type GraphRenderModel = {
  topology: MapTopology
  layout: GraphLayoutResult
  lens: IntelligenceMapLens
  caption: string
}

export type GraphNodeRenderItem = MapNode & {
  x: number
  y: number
  hidden?: boolean
  clustered?: boolean
}

export type GraphEdgeRenderItem = MapEdge & {
  from: GraphPoint
  to: GraphPoint
  hidden?: boolean
}

export type GraphRendererInput = {
  model: GraphRenderModel
  viewport: GraphViewport
  selectedNodeId: string | null
  hoveredNodeId: string | null
  hoveredEdgeId: string | null
  highlightNodeIds: Set<string>
  dimNodeIds: Set<string>
  searchMatchIds: Set<string>
  pathHighlightIds: Set<string>
  kindFilter: Set<import("@/components/intelligence/map/map-topology").MapNodeKind> | null
  reducedMotion: boolean
}

export const DEFAULT_VIEWBOX: GraphViewBox = { w: 1000, h: 520 }
export const DEFAULT_GRAPH_CENTER: GraphCenter = {
  cx: DEFAULT_VIEWBOX.w / 2,
  cy: DEFAULT_VIEWBOX.h / 2,
}

export const MIN_ZOOM = 0.35
export const MAX_ZOOM = 2.75
export const CLUSTER_THRESHOLD = 24
