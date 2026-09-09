export type FloatContentTier = "small" | "medium" | "large"

/** Window-width content tiers for Float (spec §13) — not viewport media queries. */
export function floatContentTiers(width: number): FloatContentTier {
  if (width > 0 && width < 440) return "small"
  if (width <= 620) return "medium"
  return "large"
}
