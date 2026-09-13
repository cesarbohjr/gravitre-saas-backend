/**
 * G8 — Deep-link Learning hub insights to Intelligence Overview map focus.
 */
import { APP_ROUTES } from "@/lib/app-routes"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import type { AssistantVisualization } from "@/lib/intelligence/assistant-visualization"

const VALID_LENSES = new Set<IntelligenceMapLens>([
  "knows",
  "learns",
  "predicts",
  "acts",
  "improves",
])

export function learningInsightNodeId(insightId: string): string {
  const trimmed = insightId.trim()
  if (!trimmed) return "learning:unknown"
  return trimmed.startsWith("learning:") ? trimmed : `learning:${trimmed}`
}

export function buildLearningInsightVisualization(insightId: string): AssistantVisualization {
  const nodeId = learningInsightNodeId(insightId)
  return {
    lens: "learns",
    focusNodeIds: [nodeId],
    highlightNodeIds: [nodeId],
  }
}

export function buildLearningInsightMapHref(insightId: string): string {
  const nodeId = learningInsightNodeId(insightId)
  const params = new URLSearchParams({ lens: "learns", focus: nodeId })
  return `${APP_ROUTES.intelligence}?${params.toString()}`
}

export function parseIntelligenceMapDeepLink(searchParams: URLSearchParams): {
  lens: IntelligenceMapLens | null
  focusNodeId: string | null
} {
  const focusNodeId = (searchParams.get("focus") ?? "").trim() || null
  const lensRaw = (searchParams.get("lens") ?? "").trim()
  const lens =
    lensRaw && VALID_LENSES.has(lensRaw as IntelligenceMapLens)
      ? (lensRaw as IntelligenceMapLens)
      : focusNodeId?.startsWith("learning:")
        ? "learns"
        : null
  return { lens, focusNodeId }
}
