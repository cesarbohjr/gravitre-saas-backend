import type { DashboardWidget, SizeUnits, WidgetSize } from "./types"
import { GRID_COLS, SIZE_UNITS } from "./types"

export type PlacedWidget = DashboardWidget & {
  x: number
  y: number
  w: number
  h: number
}

/**
 * Greedy left-to-right / top-to-bottom packer.
 * Deterministic collision-free placement from widget order + sizes.
 */
export function packWidgets(widgets: DashboardWidget[]): PlacedWidget[] {
  const sorted = [...widgets].sort((a, b) => a.order - b.order)
  const occupancy: boolean[][] = []

  const ensureRows = (rows: number) => {
    while (occupancy.length < rows) {
      occupancy.push(Array.from({ length: GRID_COLS }, () => false))
    }
  }

  const fits = (x: number, y: number, w: number, h: number) => {
    if (x + w > GRID_COLS) return false
    ensureRows(y + h)
    for (let row = y; row < y + h; row++) {
      for (let col = x; col < x + w; col++) {
        if (occupancy[row][col]) return false
      }
    }
    return true
  }

  const mark = (x: number, y: number, w: number, h: number) => {
    ensureRows(y + h)
    for (let row = y; row < y + h; row++) {
      for (let col = x; col < x + w; col++) {
        occupancy[row][col] = true
      }
    }
  }

  const placed: PlacedWidget[] = []

  for (const widget of sorted) {
    const units: SizeUnits = SIZE_UNITS[widget.size] ?? SIZE_UNITS["1x1"]
    let found: { x: number; y: number } | null = null
    let y = 0
    while (!found) {
      ensureRows(y + units.h)
      for (let x = 0; x <= GRID_COLS - units.w; x++) {
        if (fits(x, y, units.w, units.h)) {
          found = { x, y }
          break
        }
      }
      if (!found) y += 1
      if (y > 200) {
        found = { x: 0, y: occupancy.length }
      }
    }
    mark(found.x, found.y, units.w, units.h)
    placed.push({
      ...widget,
      x: found.x,
      y: found.y,
      w: units.w,
      h: units.h,
    })
  }

  return placed
}

export function nextSize(current: WidgetSize, allowed: WidgetSize[]): WidgetSize {
  if (allowed.length === 0) return current
  const idx = allowed.indexOf(current)
  if (idx < 0) return allowed[0]
  return allowed[(idx + 1) % allowed.length]
}

export function reindexOrders(widgets: DashboardWidget[]): DashboardWidget[] {
  return widgets
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((w, i) => ({ ...w, order: i }))
}

/** Move widget to a new order index; others shift (auto reflow via pack). */
export function moveWidgetOrder(
  widgets: DashboardWidget[],
  widgetId: string,
  toOrder: number,
): DashboardWidget[] {
  const sorted = reindexOrders(widgets)
  const from = sorted.findIndex((w) => w.id === widgetId)
  if (from < 0) return sorted
  const [item] = sorted.splice(from, 1)
  const clamped = Math.max(0, Math.min(toOrder, sorted.length))
  sorted.splice(clamped, 0, item)
  return sorted.map((w, i) => ({ ...w, order: i }))
}
