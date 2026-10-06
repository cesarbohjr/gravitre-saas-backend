/**
 * Map-first Intelligence overview — five lenses.
 * Each lens reconfigures the dominant map surface (not KPI cards). Labels reuse
 * the hub tab vocabulary so a lens and its tab never read as different things.
 */

export type IntelligenceMapLens = "knows" | "learns" | "predicts" | "acts" | "improves"

export const INTELLIGENCE_MAP_LENSES: Array<{
  id: IntelligenceMapLens
  label: string
  description: string
}> = [
  {
    id: "knows",
    label: "Knowledge",
    description: "Entities, relationships, and connected knowledge",
  },
  {
    id: "learns",
    label: "Models",
    description: "Training readiness and models improving over time",
  },
  {
    id: "predicts",
    label: "Forecasts",
    description: "Live predictions and risk signals by department",
  },
  {
    id: "acts",
    label: "Agents",
    description: "Agents and workflows executing right now",
  },
  {
    id: "improves",
    label: "Impact",
    description: "Measured outcomes and learning loops closing",
  },
]

export type IntelligenceLensMetrics = {
  knows: { value: string; hint: string }
  learns: { value: string; hint: string }
  predicts: { value: string; hint: string }
  acts: { value: string; hint: string }
  improves: { value: string; hint: string }
}
