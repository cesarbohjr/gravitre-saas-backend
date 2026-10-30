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
 * Nodus wiring from a department card to the core: out of the card's inner
 * edge, across, then one rounded elbow into the top or bottom of the core.
 */
export function elbowPath(dept: DepartmentId): string {
  const { x, y } = departmentPoint(dept)
  const left = x < NETWORK_VB.cx
  const top = y < NETWORK_VB.cy
  const sx = left ? CARD_EDGE_X : NETWORK_VB.w - CARD_EDGE_X
  const ex = NETWORK_VB.cx + (left ? -CORE_ENTRY_DX : CORE_ENTRY_DX)
  const ey = NETWORK_VB.cy + (top ? -CORE_HALF : CORE_HALF)
  const sy = top ? CARD_MID_Y : NETWORK_VB.h - CARD_MID_Y
  const r = ELBOW_R
  const dirX = left ? 1 : -1
  const dirY = top ? 1 : -1
  return `M ${sx} ${sy} H ${ex - dirX * r} Q ${ex} ${sy} ${ex} ${sy + dirY * r} V ${ey}`
}

/** Where wiring leaves a card and meets the core, in viewBox units. */
const CARD_EDGE_X = 186
const CARD_MID_Y = 58
const CORE_ENTRY_DX = 22
const CORE_HALF = 40
const ELBOW_R = 16

/**
 * Department ↔ core runs along the elbow wiring (reversed when the core is
 * the sender); anything else falls back to a restrained Bézier.
 */
export function bezierPath(from: PathEndpoint, to: PathEndpoint): string {
  if (from !== "core" && to === "core") return elbowPath(from)
  if (from === "core" && to !== "core") return reversePath(elbowPath(to))

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

/** Reverse an elbow path (M, H, Q, V only) so packets can travel core → card. */
function reversePath(d: string): string {
  const m = d.match(/M (\S+) (\S+) H (\S+) Q (\S+) (\S+) (\S+) (\S+) V (\S+)/)
  if (!m) return d
  const [, sx, sy, hx, qx, qy, ex, ey2, vy] = m
  return `M ${ex} ${vy} V ${ey2} Q ${qx} ${qy} ${hx} ${sy} H ${sx}`
}

export const DEPARTMENT_EDGE_KEYS: { dept: DepartmentId; d: string }[] = (
  ["sales", "support", "operations", "finance"] as DepartmentId[]
).map((dept) => ({
  dept,
  d: elbowPath(dept),
}))
