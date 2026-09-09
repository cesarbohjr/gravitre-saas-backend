import { DEPARTMENT_XY, NETWORK_VB, type DepartmentId, type PathEndpoint } from "./types"

export type Pt = { x: number; y: number }

export function departmentPoint(id: DepartmentId): Pt {
  return DEPARTMENT_XY[id]
}

export function endpointPoint(ep: PathEndpoint): Pt {
  if (ep === "core") return { x: NETWORK_VB.cx, y: NETWORK_VB.cy }
  return departmentPoint(ep)
}

/**
 * Cubic Bézier from department ↔ core — restrained curve (not a straight spoke).
 */
export function bezierPath(from: PathEndpoint, to: PathEndpoint): string {
  const a = endpointPoint(from)
  const b = endpointPoint(to)
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const ox = (-dy / len) * len * 0.12
  const oy = (dx / len) * len * 0.12
  const c1x = a.x + dx * 0.35 + ox
  const c1y = a.y + dy * 0.35 + oy
  const c2x = a.x + dx * 0.65 + ox
  const c2y = a.y + dy * 0.65 + oy
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`
}

export function pathKey(from: PathEndpoint, to: PathEndpoint): string {
  return [from, to].sort().join("--")
}

export const DEPARTMENT_EDGE_KEYS: { dept: DepartmentId; d: string }[] = (
  ["sales", "support", "operations", "finance"] as DepartmentId[]
).map((dept) => ({
  dept,
  d: bezierPath(dept, "core"),
}))
