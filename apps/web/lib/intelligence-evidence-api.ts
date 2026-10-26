/** Dedicated Intelligence API additions, isolated from the shared client merge surface. */
import { fetcher, apiFetch } from "@/lib/fetcher"

function apiUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "")
  if (!base) return path
  return path.startsWith("/api/") && base.endsWith("/api") ? `${base}${path.slice(4)}` : `${base}${path}`
}

async function postJson<T>(url: string, data: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return (await response.json()) as T
}

export type EvidenceRecommendation = {
  id: string
  title: string
  description: string
  kind: string
  sources: Array<{ connector_id: string; object_type: string; external_id: string }>
  recommended_play_key: string
  advisory_only: boolean
  approval_required: boolean
  business_impact: number | null
  outcome_verified: boolean
}

export const intelligenceEvidenceApi = {
  sweepUsage: () => fetcher<{
    period: string
    limit: number
    used: number
    remaining: number
    unit: string
  }>(apiUrl("/api/intelligence/overview/sweep-usage")),
  evidenceRecommendations: () =>
    fetcher<{ recommendations: EvidenceRecommendation[]; count: number; advisoryOnly: boolean }>(
      apiUrl("/api/intelligence/overview/evidence-recommendations"),
    ),
  evidenceRecommendationHandoffs: (recommendationId: string) =>
    fetcher<{
      recommendationId: string
      handoffs: Array<{
        handoffId: string
        playKey: string
        playRunId: string | null
        status: string
        verifiedBusinessOutcome: boolean
        outcomes: Array<{ outcomeId: string; verified: boolean; verificationState: string }>
      }>
      count: number
    }>(apiUrl(`/api/intelligence/overview/evidence-recommendations/${encodeURIComponent(recommendationId)}/handoffs`)),
  runEvidenceRecommendation: (recommendationId: string, installationId: string) =>
    postJson<{
      recommendationId: string
      playKey: string
      playRun: Record<string, unknown>
      verifiedBusinessOutcome: boolean
      outcomesHref: string
    }>(
      apiUrl(`/api/intelligence/overview/evidence-recommendations/${encodeURIComponent(recommendationId)}/play-runs`),
      { installation_id: installationId },
    ),
}
