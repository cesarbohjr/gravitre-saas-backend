import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"

/** Mirror of backend `LENS_NODE_EMPHASIS` — one graph, lens-filtered emphasis. */
export const LENS_NODE_EMPHASIS: Record<IntelligenceMapLens, ReadonlySet<string>> = {
  knows: new Set(["core", "entity", "knowledge", "domain", "connector"]),
  learns: new Set(["core", "learning", "model", "outcome", "memory"]),
  predicts: new Set(["core", "prediction", "signal", "evidence", "objective", "domain"]),
  acts: new Set(["core", "agent", "workflow", "action", "connector", "approval", "domain"]),
  improves: new Set(["core", "outcome", "objective", "learning", "domain"]),
}

export function nodeMatchesLens(nodeType: string, lens: IntelligenceMapLens): boolean {
  return LENS_NODE_EMPHASIS[lens].has(nodeType)
}
