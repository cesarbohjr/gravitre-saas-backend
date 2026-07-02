/** Shared chart colors aligned with Gravitre emerald/teal brand tokens. */
export const CHART_EMERALD = "#10b981"
export const CHART_TEAL = "#14b8a6"
export const CHART_VIOLET = "#8b5cf6"

export function progressBarClass(value: number): string {
  if (value >= 75) return "bg-emerald-500"
  if (value >= 50) return "bg-amber-500"
  return "bg-orange-500"
}

export function cacheHitBarClass(rate: number): string {
  if (rate >= 0.6) return "bg-emerald-500"
  if (rate >= 0.25) return "bg-amber-500"
  return "bg-orange-500"
}

/** Cubic ease-out for count-up / grow animations. */
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3)
}
