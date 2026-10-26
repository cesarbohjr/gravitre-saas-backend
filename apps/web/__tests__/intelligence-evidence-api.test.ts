import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/fetcher", () => ({
  fetcher: vi.fn(),
  apiFetch: vi.fn(),
}))
vi.mock("@/lib/agent-interrupts", () => ({
  requestAgentInterrupt: vi.fn(),
}))

import { apiFetch, fetcher } from "@/lib/fetcher"
import { intelligenceEvidenceApi } from "@/lib/intelligence-evidence-api"

describe("Intelligence evidence recommendation API wiring", () => {
  beforeEach(() => vi.clearAllMocks())

  it("fetches recommendations through the authenticated API helper", async () => {
    vi.mocked(fetcher).mockResolvedValueOnce({ recommendations: [], count: 0, advisoryOnly: true })
    const result = await intelligenceEvidenceApi.evidenceRecommendations()
    expect(result.count).toBe(0)
    expect(vi.mocked(fetcher).mock.calls[0][0]).toContain("/api/intelligence/overview/evidence-recommendations")
  })

  it("starts only the canonical governed recommendation handoff with an installation", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce(new Response(
      JSON.stringify({ recommendationId: "rec-1", playKey: "customer-rescue",
        playRun: { status: "awaiting_approval" }, verifiedBusinessOutcome: false }),
      { status: 200, headers: { "content-type": "application/json" } },
    ))
    const result = await intelligenceEvidenceApi.runEvidenceRecommendation("rec/1", "installed-a")
    expect(result.verifiedBusinessOutcome).toBe(false)
    const [url, request] = vi.mocked(apiFetch).mock.calls[0]
    expect(url).toContain("/evidence-recommendations/rec%2F1/play-runs")
    expect(request?.method).toBe("POST")
    expect(JSON.parse(String(request?.body))).toEqual({ installation_id: "installed-a" })
  })

  it("fetches source-verified outcome readback rather than inferring success", async () => {
    vi.mocked(fetcher).mockResolvedValueOnce({ recommendationId: "rec-1", handoffs: [], count: 0 })
    await intelligenceEvidenceApi.evidenceRecommendationHandoffs("rec-1")
    expect(vi.mocked(fetcher).mock.calls[0][0]).toContain(
      "/api/intelligence/overview/evidence-recommendations/rec-1/handoffs",
    )
  })
})
