import { CLUSTER_THRESHOLD, type GraphPoint } from "./types"

export const LABEL_LOD_MIN_SCALE = 0.72
export const NODE_COLLISION_PX = 56
export const LABEL_BOX = { w: 152, h: 40 }

export function isDenseGraph(nodeCount: number): boolean {
  return nodeCount >= CLUSTER_THRESHOLD
}

export function shouldShowNodeLabel(options: {
  scale: number
  dense: boolean
  selected?: boolean
  highlighted?: boolean
  hovered?: boolean
}): boolean {
  if (options.selected || options.highlighted || options.hovered) return true
  if (options.scale < LABEL_LOD_MIN_SCALE) return false
  if (options.dense && options.scale < 1) return false
  return true
}

/**
 * Separate overlapping node centers. Pure layout step — does not invent product data.
 */
export function resolveNodeCollisions(
  positions: Map<string, GraphPoint>,
  minSep = NODE_COLLISION_PX,
  iterations = 8,
): Map<string, GraphPoint> {
  const next = new Map(positions)
  const ids = [...next.keys()]
  for (let iter = 0; iter < iterations; iter += 1) {
    let moved = false
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const aId = ids[i]!
        const bId = ids[j]!
        const a = next.get(aId)
        const b = next.get(bId)
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.hypot(dx, dy) || 0.01
        if (dist >= minSep) continue
        const push = (minSep - dist) / 2
        const nx = dx / dist
        const ny = dy / dist
        next.set(aId, { x: a.x - nx * push, y: a.y - ny * push })
        next.set(bId, { x: b.x + nx * push, y: b.y + ny * push })
        moved = true
      }
    }
    if (!moved) break
  }
  return next
}

export function labelsOverlap(
  a: GraphPoint,
  b: GraphPoint,
  box = LABEL_BOX,
): boolean {
  return Math.abs(a.x - b.x) < box.w && Math.abs(a.y - b.y) < box.h
}
