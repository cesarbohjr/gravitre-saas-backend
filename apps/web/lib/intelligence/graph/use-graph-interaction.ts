"use client"

import { useCallback, useMemo, useReducer, useRef } from "react"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"
import {
  createInitialInteractionState,
  graphInteractionController,
  type GraphInteractionState,
} from "./graph-interaction-controller"
import { DEFAULT_VIEWBOX, type GraphPoint, type GraphViewport } from "./types"

type DragMode =
  | { kind: "pan"; startX: number; startY: number; origin: GraphViewport }
  | { kind: "node"; nodeId: string; startX: number; startY: number; origin: GraphPoint }
  | null

type Action =
  | { type: "set"; patch: Partial<GraphInteractionState> }
  | { type: "viewport"; viewport: GraphViewport }
  | { type: "reset-viewport" }

function reducer(state: GraphInteractionState, action: Action): GraphInteractionState {
  switch (action.type) {
    case "set":
      return { ...state, ...action.patch }
    case "viewport":
      return { ...state, viewport: action.viewport }
    case "reset-viewport":
      return { ...state, viewport: graphInteractionController.resetViewport() }
    default:
      return state
  }
}

export function useGraphInteraction(initial?: Partial<GraphInteractionState>) {
  const [state, dispatch] = useReducer(reducer, createInitialInteractionState(initial))
  const dragRef = useRef<DragMode>(null)

  const setSelectedNodeId = useCallback((selectedNodeId: string | null) => {
    dispatch({
      type: "set",
      patch: {
        selectedNodeId,
        focusNodeIds: selectedNodeId ? [selectedNodeId] : [],
      },
    })
  }, [])

  const setHoveredNodeId = useCallback((hoveredNodeId: string | null) => {
    dispatch({ type: "set", patch: { hoveredNodeId } })
  }, [])

  const setHoveredEdgeId = useCallback((hoveredEdgeId: string | null) => {
    dispatch({ type: "set", patch: { hoveredEdgeId } })
  }, [])

  const zoomIn = useCallback(() => {
    dispatch({
      type: "viewport",
      viewport: graphInteractionController.zoomIn(state.viewport),
    })
  }, [state.viewport])

  const zoomOut = useCallback(() => {
    dispatch({
      type: "viewport",
      viewport: graphInteractionController.zoomOut(state.viewport),
    })
  }, [state.viewport])

  const resetViewport = useCallback(() => {
    dispatch({ type: "reset-viewport" })
  }, [])

  const fitToView = useCallback((positions: Map<string, GraphPoint>, nodeIds?: string[]) => {
    const viewport = graphInteractionController.fitToView(
      positions,
      nodeIds ?? [...positions.keys()],
    )
    if (viewport) dispatch({ type: "viewport", viewport })
  }, [])

  const focusNode = useCallback(
    (positions: Map<string, GraphPoint>, nodeId: string) => {
      const viewport = graphInteractionController.focusNode(positions, nodeId)
      if (viewport) dispatch({ type: "viewport", viewport })
      dispatch({ type: "set", patch: { selectedNodeId: nodeId, focusNodeIds: [nodeId] } })
    },
    [],
  )

  const togglePin = useCallback((nodeId: string, position?: GraphPoint) => {
    dispatch({
      type: "set",
      patch: graphInteractionController.togglePin(state, nodeId, position),
    })
  }, [state])

  const toggleCluster = useCallback((clusterId: string) => {
    dispatch({
      type: "set",
      patch: graphInteractionController.toggleCluster(state, clusterId),
    })
  }, [state])

  const setKindFilter = useCallback((kinds: Set<MapNodeKind> | null) => {
    dispatch({
      type: "set",
      patch: graphInteractionController.setKindFilter(state, kinds),
    })
  }, [state])

  const setSearchQuery = useCallback((searchQuery: string) => {
    dispatch({
      type: "set",
      patch: graphInteractionController.setSearchQuery(state, searchQuery),
    })
  }, [state])

  /**
   * Scroll belongs to the page. The graph only zooms on a deliberate gesture:
   * Ctrl/⌘ + wheel, or a trackpad pinch (which browsers report as ctrlKey).
   * Returns true when the event was used for zoom so the caller can
   * preventDefault; otherwise the caller lets the page scroll and may show a hint.
   */
  const handleWheel = useCallback(
    (event: Pick<WheelEvent, "deltaY" | "ctrlKey" | "metaKey">): boolean => {
      if (!event.ctrlKey && !event.metaKey) return false
      const delta = event.deltaY < 0 ? 1 : -1
      dispatch({
        type: "viewport",
        viewport: graphInteractionController.zoomAt(state.viewport, delta),
      })
      return true
    },
    [state.viewport],
  )

  const beginPan = useCallback(
    (clientX: number, clientY: number) => {
      dragRef.current = {
        kind: "pan",
        startX: clientX,
        startY: clientY,
        origin: { ...state.viewport },
      }
    },
    [state.viewport],
  )

  const beginNodeDrag = useCallback(
    (nodeId: string, clientX: number, clientY: number, origin: GraphPoint) => {
      dragRef.current = {
        kind: "node",
        nodeId,
        startX: clientX,
        startY: clientY,
        origin: { ...origin },
      }
    },
    [],
  )

  /**
   * `surface` is the unscaled pixel size of the graph surface. Viewport
   * translate is a percentage of that surface, so a pan follows the pointer 1:1;
   * node drags convert pixels into layout (viewBox) units at the current zoom.
   */
  const moveDrag = useCallback(
    (
      clientX: number,
      clientY: number,
      scale: number,
      onNodeDrag?: (nodeId: string, point: GraphPoint) => void,
      surface?: { width: number; height: number },
    ) => {
      const drag = dragRef.current
      if (!drag) return
      const width = surface?.width || DEFAULT_VIEWBOX.w
      const height = surface?.height || DEFAULT_VIEWBOX.h
      const dxPx = clientX - drag.startX
      const dyPx = clientY - drag.startY
      if (drag.kind === "pan") {
        dispatch({
          type: "viewport",
          viewport: {
            ...drag.origin,
            translateX: drag.origin.translateX + (dxPx / width) * 100,
            translateY: drag.origin.translateY + (dyPx / height) * 100,
          },
        })
      } else if (drag.kind === "node" && onNodeDrag) {
        onNodeDrag(drag.nodeId, {
          x: drag.origin.x + (dxPx / scale) * (DEFAULT_VIEWBOX.w / width),
          y: drag.origin.y + (dyPx / scale) * (DEFAULT_VIEWBOX.h / height),
        })
      }
    },
    [],
  )

  const endDrag = useCallback(() => {
    dragRef.current = null
  }, [])

  const cycleKeyboardFocus = useCallback(
    (visibleNodeIds: string[], direction: 1 | -1) => {
      dispatch({
        type: "set",
        patch: graphInteractionController.cycleKeyboardFocus(state, visibleNodeIds, direction),
      })
    },
    [state],
  )

  const api = useMemo(
    () => ({
      state,
      setSelectedNodeId,
      setHoveredNodeId,
      setHoveredEdgeId,
      zoomIn,
      zoomOut,
      resetViewport,
      fitToView,
      focusNode,
      togglePin,
      toggleCluster,
      setKindFilter,
      setSearchQuery,
      handleWheel,
      beginPan,
      beginNodeDrag,
      moveDrag,
      endDrag,
      cycleKeyboardFocus,
    }),
    [
      state,
      setSelectedNodeId,
      setHoveredNodeId,
      setHoveredEdgeId,
      zoomIn,
      zoomOut,
      resetViewport,
      fitToView,
      focusNode,
      togglePin,
      toggleCluster,
      setKindFilter,
      setSearchQuery,
      handleWheel,
      beginPan,
      beginNodeDrag,
      moveDrag,
      endDrag,
      cycleKeyboardFocus,
    ],
  )

  return api
}
