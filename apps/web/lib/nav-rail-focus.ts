/** Roving focus index for Navigation B keyboard rail. */
export function cycleNavFocus(current: number, delta: number, length: number): number {
  if (length <= 0) return 0
  const base = current < 0 ? (delta > 0 ? -1 : 0) : current
  return (base + delta + length) % length
}
