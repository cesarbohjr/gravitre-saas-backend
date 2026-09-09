import { DEPARTMENT_META, NETWORK_VB, NODE_RADIUS, type DepartmentId, type PathEndpoint } from "./types"

export type Pt = { x: number; y: number }

export function departmentPoint(id: DepartmentId): Pt {
  const rad = (DEPARTMENT_META[id].angle * Math.PI) / 180
  return {
    x: NETWORK_VB.cx + Math.cos(rad) * NODE_RADIUS,
    y: NETWORK_VB.cy + Math.sin(rad) * NODE_RADIUS,
  }
}

export function endpointPoint(ep: PathEndpoint): Pt {
  if (ep === "core") return { x: NETWORK_VB.cx, y: NETWORK_VB.cy }
  return departmentPoint(ep)
}

/**
 * Elegant cubic Bézier from department ↔ core.
 * Control points pull slightly perpendicular so paths fan instead of radiating as straight spokes.
 */
export function bezierPath(from: PathEndpoint, to: PathEndpoint): string {
  const a = endpointPoint(from)
  const b = endpointPoint(to)
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  // Perpendicular offset (~14% of span) for a restrained mineral curve
  const ox = (-dy / len) * len * 0.14
  const oy = (dx / len) * len * 0.14
  const c1x = a.x + dx * 0.35 + ox
  const c1y = a.y + dy * 0.35 + oy
  const c2x = a.x + dx * 0.65 + ox
  const c2y = a.y + dy * 0.65 + oy
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`
}

export function pathKey(from: PathEndpoint, to: PathEndpoint): string {
  const pair = [from, to].sort().join("--")
  return pair
}

/** Canonical undirected edge keys for the four departments ↔ core */
export const DEPARTMENT_EDGE_KEYS: { dept: DepartmentId; d: string }[] = (
  ["sales", "support", "operations", "finance"] as DepartmentId[]
).map((dept) => ({
  dept,
  d: bezierPath(dept, "core"),
}))
