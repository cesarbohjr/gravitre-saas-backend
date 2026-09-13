/** Phase F — compute zoom/pan transform to focus highlighted map nodes. */

export type MapSpatialTransform = {
  scale: number
  translateX: number
  translateY: number
}

export function computeMapFocusTransform(
  highlightNodeIds: string[],
  positions: Map<string, { x: number; y: number }>,
  center: { cx: number; cy: number },
  viewBox: { w: number; h: number },
): MapSpatialTransform | null {
  if (highlightNodeIds.length === 0) return null

  const points = highlightNodeIds
    .map((id) => positions.get(id))
    .filter((p): p is { x: number; y: number } => p != null)
  if (points.length === 0) return null

  points.push({ x: center.cx, y: center.cy })

  let minX = points[0]!.x
  let maxX = points[0]!.x
  let minY = points[0]!.y
  let maxY = points[0]!.y
  for (const p of points) {
    minX = Math.min(minX, p.x)
    maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y)
    maxY = Math.max(maxY, p.y)
  }

  const pad = 80
  const boxW = Math.max(maxX - minX + pad * 2, 120)
  const boxH = Math.max(maxY - minY + pad * 2, 120)
  const scale = Math.min(1.65, Math.min(viewBox.w / boxW, viewBox.h / boxH))

  const focusCx = (minX + maxX) / 2
  const focusCy = (minY + maxY) / 2
  const translateX = ((viewBox.w / 2 - focusCx) / viewBox.w) * 100 * scale
  const translateY = ((viewBox.h / 2 - focusCy) / viewBox.h) * 100 * scale

  return { scale, translateX, translateY }
}
