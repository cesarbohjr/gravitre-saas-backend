/**
 * Creative Experience System — design tokens (Pilot 1+).
 * Brand green is exact #16a374 — never invent alternate greens here.
 */

export const CREATIVE_BRAND = "#16a374" as const

export const CREATIVE_TOKENS = {
  brand: CREATIVE_BRAND,
  signal: "var(--color-blue-500)",
  intelligence: "var(--g-intelligence)",
  action: "var(--color-brand, #16a374)",
  learn: "color-mix(in oklch, var(--g-intelligence) 55%, #7c6af5)",
  mineralLine: "var(--color-line, #eaedf1)",
  nodeIdle: 4,
  nodeActive: 5.5,
  traceIdle: 1.25,
  traceActive: 2,
  traceLearned: 1.75,
  signalCapsuleW: 16,
  signalCapsuleH: 5.5,
  spring: { stiffness: 280, damping: 28 },
  durationsMs: {
    assemble: 900,
    transfer: 1100,
    verify: 700,
    learn: 900,
    settle: 800,
  },
} as const

export type CreativeQuality = "high" | "medium" | "low" | "fallback"
