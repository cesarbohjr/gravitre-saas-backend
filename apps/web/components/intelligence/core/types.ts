/**
 * Gravitre Intelligence Core (Phase 2, 2026-09-11) — real, state-driven visualization.
 *
 * Reuses the visual signature proven in the marketing department-network component
 * (components/marketing/system/department-network) — CSS + SVG + Framer Motion, no
 * WebGL/Three.js (per redesign decision #5). Unlike that marketing component, every
 * state here comes from GET /api/intelligence/core/state — there is no scripted
 * story engine and no fixed 4-department set: department nodes only render for
 * departments the backend actually reports real recent activity for.
 */
import type { IntelligenceCoreVisualState } from "@/lib/api"

export const CORE_STATE_LABEL: Record<IntelligenceCoreVisualState, string> = {
  idle: "Idle",
  "flow-inward": "New activity",
  trace: "Agents active",
  "pending-approval": "Awaiting approval",
  resolved: "Resolved",
  "low-confidence": "Low confidence",
}

export const CORE_STATE_ACCENT: Record<IntelligenceCoreVisualState, string> = {
  idle: "var(--color-line, #eaedf1)",
  "flow-inward": "var(--color-blue-500)",
  trace: "var(--color-brand, #16a374)",
  "pending-approval": "#d97706",
  resolved: "var(--color-brand, #16a374)",
  "low-confidence": "#94a3b8",
}

/** Title-cases a raw department id from the backend (e.g. "customer_success" -> "Customer Success"). */
export function formatDepartmentLabel(id: string): string {
  return id
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

/** Evenly spaces `count` nodes on a circle of `radius` around (cx, cy), starting at the top. */
export function radialLayout(
  count: number,
  { cx, cy, radius }: { cx: number; cy: number; radius: number },
): Array<{ x: number; y: number }> {
  if (count <= 0) return []
  return Array.from({ length: count }, (_, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
  })
}
