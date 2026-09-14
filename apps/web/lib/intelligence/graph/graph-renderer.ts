import { CORE_ID, type MapEdge, type MapNode } from "@/components/intelligence/map/map-topology"
import type {
  GraphEdgeRenderItem,
  GraphNodeRenderItem,
  GraphRenderModel,
  GraphRendererInput,
} from "./types"

/**
 * I2 — renderer adapter interface. DOM/SVG and WebGL implementations stay behind this.
 */
export interface GraphRenderer {
  readonly id: string
  prepare(input: GraphRendererInput): {
    nodes: GraphNodeRenderItem[]
    edges: GraphEdgeRenderItem[]
    corePosition: { x: number; y: number }
  }
}

export class DomSvgGraphRenderer implements GraphRenderer {
  readonly id = "dom-svg"

  prepare(input: GraphRendererInput): {
    nodes: GraphNodeRenderItem[]
    edges: GraphEdgeRenderItem[]
    corePosition: { x: number; y: number }
  } {
    const { model, kindFilter } = input
    const { positions } = model.layout

    const nodes: GraphNodeRenderItem[] = model.topology.nodes
      .map((node) => {
        const pos = positions.get(node.id)
        if (!pos) return null
        if (kindFilter && kindFilter.size > 0 && !kindFilter.has(node.kind)) {
          return { ...node, x: pos.x, y: pos.y, hidden: true }
        }
        return { ...node, x: pos.x, y: pos.y, hidden: false }
      })
      .filter((node): node is GraphNodeRenderItem => node != null)

    const edges: GraphEdgeRenderItem[] = model.topology.edges
      .map((edge) => {
        const fromId = edge.fromId === CORE_ID ? CORE_ID : edge.fromId
        const toId = edge.toId === CORE_ID ? CORE_ID : edge.toId
        const from = positions.get(fromId)
        const to = positions.get(toId)
        if (!from || !to) return null
        const fromHidden = nodes.find((n) => n.id === fromId)?.hidden
        const toHidden = nodes.find((n) => n.id === toId)?.hidden
        return {
          ...edge,
          from,
          to,
          hidden: Boolean(fromHidden || toHidden),
        }
      })
      .filter((edge): edge is GraphEdgeRenderItem => edge != null)

    const corePosition = positions.get(CORE_ID) ?? { x: 500, y: 260 }

    return { nodes, edges, corePosition }
  }
}

export function buildRenderPayload(
  renderer: GraphRenderer,
  input: GraphRendererInput,
): ReturnType<GraphRenderer["prepare"]> {
  return renderer.prepare(input)
}

export type { GraphRenderModel, GraphRendererInput }
