/**
 * I9 — Optional 2.5D spatial projection. Adapter only; semantics stay in IntelligenceGraph.
 */
import { CORE_ID } from "@/components/intelligence/map/map-topology"
import type { GraphRenderer, GraphRendererInput } from "../graph-renderer"
import { DomSvgGraphRenderer } from "../graph-renderer"
import type { GraphPoint } from "../types"
import { DEFAULT_VIEWBOX } from "../types"

export type SpatialProjectionOptions = {
  tilt?: number
}

/** Pure projection used by the spatial renderer and unit tests. */
export function projectSpatialPoint(
  point: GraphPoint,
  view = DEFAULT_VIEWBOX,
  options: SpatialProjectionOptions = {},
): GraphPoint {
  const tilt = options.tilt ?? 0.28
  const cx = view.w / 2
  const cy = view.h / 2
  const depth = (point.y - cy) / view.h
  const scale = 1 - depth * 0.22
  return {
    x: cx + (point.x - cx) * scale,
    y: point.y * (1 - tilt * 0.18) + tilt * 36,
  }
}

export class SpatialGraphRenderer implements GraphRenderer {
  readonly id = "spatial-2.5d"
  private readonly base = new DomSvgGraphRenderer()

  prepare(input: GraphRendererInput) {
    const prepared = this.base.prepare(input)
    if (input.reducedMotion) return prepared
    const nodes = prepared.nodes.map((node) => {
      const projected = projectSpatialPoint({ x: node.x, y: node.y })
      return { ...node, x: projected.x, y: projected.y }
    })
    const byId = new Map(nodes.map((n) => [n.id, n]))
    const edges = prepared.edges.map((edge) => {
      const fromNode = byId.get(edge.fromId === CORE_ID ? CORE_ID : edge.fromId)
      const toNode = byId.get(edge.toId === CORE_ID ? CORE_ID : edge.toId)
      return {
        ...edge,
        from: fromNode ? { x: fromNode.x, y: fromNode.y } : projectSpatialPoint(edge.from),
        to: toNode ? { x: toNode.x, y: toNode.y } : projectSpatialPoint(edge.to),
      }
    })
    const core = byId.get(CORE_ID)
    return {
      nodes,
      edges,
      corePosition: core ? { x: core.x, y: core.y } : projectSpatialPoint(prepared.corePosition),
    }
  }
}
