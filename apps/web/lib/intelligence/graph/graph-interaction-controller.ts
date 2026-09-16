import { computeMapFocusTransform } from "@/components/intelligence/map/map-spatial-focus"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"
import {
  DEFAULT_GRAPH_CENTER,
  DEFAULT_VIEWBOX,
  MAX_ZOOM,
  MIN_ZOOM,
  type GraphPoint,
  type GraphViewport,
} from "./types"

export type GraphInteractionState = {
  viewport: GraphViewport
  selectedNodeId: string | null
  hoveredNodeId: string | null
  hoveredEdgeId: string | null
  pinnedNodeIds: Set<string>
  pinnedPositions: Map<string, GraphPoint>
  collapsedClusterIds: Set<string>
  expandedClusterIds: Set<string>
  kindFilter: Set<MapNodeKind> | null
  searchQuery: string
  focusNodeIds: string[]
  keyboardFocusIndex: number
}

export const DEFAULT_VIEWPORT: GraphViewport = {
  scale: 1,
  translateX: 0,
  translateY: 0,
}

export function createInitialInteractionState(
  partial?: Partial<GraphInteractionState>,
): GraphInteractionState {
  return {
    viewport: { ...DEFAULT_VIEWPORT },
    selectedNodeId: null,
    hoveredNodeId: null,
    hoveredEdgeId: null,
    pinnedNodeIds: new Set(),
    pinnedPositions: new Map(),
    collapsedClusterIds: new Set(),
    expandedClusterIds: new Set(),
    kindFilter: null,
    searchQuery: "",
    focusNodeIds: [],
    keyboardFocusIndex: -1,
    ...partial,
  }
}

function clampZoom(scale: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, scale))
}

/**
 * I2 — pure interaction logic (renderer-agnostic).
 */
export class GraphInteractionController {
  zoomAt(
    viewport: GraphViewport,
    delta: number,
    _anchor?: GraphPoint,
  ): GraphViewport {
    const nextScale = clampZoom(viewport.scale * (delta > 0 ? 1.12 : 0.89))
    return { ...viewport, scale: nextScale }
  }

  zoomIn(viewport: GraphViewport): GraphViewport {
    return this.zoomAt(viewport, 1)
  }

  zoomOut(viewport: GraphViewport): GraphViewport {
    return this.zoomAt(viewport, -1)
  }

  pan(viewport: GraphViewport, dx: number, dy: number): GraphViewport {
    return {
      ...viewport,
      translateX: viewport.translateX + dx,
      translateY: viewport.translateY + dy,
    }
  }

  resetViewport(): GraphViewport {
    return { ...DEFAULT_VIEWPORT }
  }

  fitToView(
    positions: Map<string, GraphPoint>,
    nodeIds: string[],
  ): GraphViewport | null {
    const transform = computeMapFocusTransform(
      nodeIds.length > 0 ? nodeIds : [...positions.keys()],
      positions,
      DEFAULT_GRAPH_CENTER,
      DEFAULT_VIEWBOX,
    )
    if (!transform) return null
    return {
      scale: clampZoom(transform.scale),
      translateX: transform.translateX,
      translateY: transform.translateY,
    }
  }

  focusNode(
    positions: Map<string, GraphPoint>,
    nodeId: string,
    includeNeighbors = true,
  ): GraphViewport | null {
    const ids = includeNeighbors
      ? [...positions.keys()].filter((id) => {
          if (id === nodeId) return true
          return false
        })
      : [nodeId]
    return this.fitToView(positions, ids.length ? [nodeId] : [])
  }

  togglePin(
    state: GraphInteractionState,
    nodeId: string,
    position?: GraphPoint,
  ): GraphInteractionState {
    const pinnedNodeIds = new Set(state.pinnedNodeIds)
    const pinnedPositions = new Map(state.pinnedPositions)
    if (pinnedNodeIds.has(nodeId)) {
      pinnedNodeIds.delete(nodeId)
      pinnedPositions.delete(nodeId)
    } else {
      pinnedNodeIds.add(nodeId)
      if (position) pinnedPositions.set(nodeId, position)
    }
    return { ...state, pinnedNodeIds, pinnedPositions }
  }

  toggleCluster(
    state: GraphInteractionState,
    clusterId: string,
  ): GraphInteractionState {
    const expandedClusterIds = new Set(state.expandedClusterIds)
    if (expandedClusterIds.has(clusterId)) expandedClusterIds.delete(clusterId)
    else expandedClusterIds.add(clusterId)
    return { ...state, expandedClusterIds }
  }

  setKindFilter(
    state: GraphInteractionState,
    kinds: Set<MapNodeKind> | null,
  ): GraphInteractionState {
    return { ...state, kindFilter: kinds }
  }

  setSearchQuery(state: GraphInteractionState, query: string): GraphInteractionState {
    return { ...state, searchQuery: query, keyboardFocusIndex: -1 }
  }

  cycleKeyboardFocus(
    state: GraphInteractionState,
    visibleNodeIds: string[],
    direction: 1 | -1,
  ): GraphInteractionState {
    if (visibleNodeIds.length === 0) return state
    const nextIndex =
      state.keyboardFocusIndex < 0
        ? 0
        : (state.keyboardFocusIndex + direction + visibleNodeIds.length) %
          visibleNodeIds.length
    const selectedNodeId = visibleNodeIds[nextIndex] ?? null
    return {
      ...state,
      keyboardFocusIndex: nextIndex,
      selectedNodeId,
      focusNodeIds: selectedNodeId ? [selectedNodeId] : [],
    }
  }

  hoverPathNodeIds(
    graphConnected: (nodeId: string) => Set<string>,
    hoveredNodeId: string | null,
  ): Set<string> {
    if (!hoveredNodeId) return new Set()
    const path = graphConnected(hoveredNodeId)
    path.add(hoveredNodeId)
    return path
  }
}

export const graphInteractionController = new GraphInteractionController()
