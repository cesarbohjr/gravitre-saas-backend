import { describe, expect, it } from "vitest"
import {
  buildMemoryLearningClaim,
  buildQueryClusterClaim,
  buildRetrievalRankerClaim,
  buildOperationalSuccessClaim,
  formatLiveConfidencePercent,
  EMPTY_LIVE_INTEL,
} from "@/lib/marketing-intelligence-truth"

describe("marketing-intelligence-truth", () => {
  it("never fabricates a retrieval TRAINED percentage without a loaded artifact", () => {
    const claim = buildRetrievalRankerClaim(EMPTY_LIVE_INTEL)
    expect(claim.primary).not.toMatch(/\d+\s*%/)
    expect(claim.primary).not.toMatch(/TRAINED/i)
    expect(["heuristic", "data_gate"]).toContain(claim.provenance)
  })

  it("shows live confidence only when artifact is loaded and not an estimate", () => {
    expect(
      formatLiveConfidencePercent({
        confidence: 0.84,
        confidenceIsEstimate: false,
        artifactLoaded: true,
        liveInferencePath: "loaded_model_artifact",
        sampleSize: 120,
      }),
    ).toBe("84%")
    expect(
      formatLiveConfidencePercent({
        confidence: 0.84,
        confidenceIsEstimate: true,
        artifactLoaded: true,
      }),
    ).toBeNull()
    expect(
      formatLiveConfidencePercent({
        confidence: 0.84,
        confidenceIsEstimate: false,
        artifactLoaded: false,
      }),
    ).toBeNull()
  })

  it("uses directional query-cluster copy without invented counts", () => {
    const claim = buildQueryClusterClaim(EMPTY_LIVE_INTEL)
    expect(claim.primary).not.toMatch(/\d+\s+themes/)
    expect(claim.provenance).toBe("directional")
  })

  it("memory claim defaults to honest directional language", () => {
    const claim = buildMemoryLearningClaim(EMPTY_LIVE_INTEL)
    expect(claim.primary).toMatch(/learns from every approved action/i)
    expect(claim.primary).not.toMatch(/\d+\s*%/)
  })

  it("operational success refuses empty-data percentages", () => {
    const claim = buildOperationalSuccessClaim(EMPTY_LIVE_INTEL)
    expect(claim.primary).not.toMatch(/\d+\s*%/)
    expect(claim.provenance).toBe("directional")
  })
})
