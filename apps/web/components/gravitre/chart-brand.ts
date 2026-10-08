/**
 * Shared chart colors aligned with Brand Foundation (Figma 01). These resolve
 * to the global theme tokens (app/globals.css) so SVG fills/stops follow the
 * light and dark themes instead of shipping hard-coded hex.
 */
export const CHART_EMERALD = "var(--g-brand)"
export const CHART_TEAL = "var(--chart-1)"
export const CHART_VIOLET = "var(--chart-4)"

export function progressBarClass(value: number): string {
  if (value >= 75) return "bg-success"
  if (value >= 50) return "bg-chart-3"
  return "bg-warning"
}

export function cacheHitBarClass(rate: number): string {
  if (rate >= 0.6) return "bg-success"
  if (rate >= 0.25) return "bg-chart-3"
  return "bg-warning"
}

/** Cubic ease-out for count-up / grow animations. */
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3)
}
