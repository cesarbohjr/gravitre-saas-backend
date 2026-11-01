import { describe, expect, it } from "vitest"
import {
  CANCELLATION_LIMIT_MS,
  LOCAL_KWS_SHADOW_ONLY,
  evaluateLocalCancelCandidate,
  type CancellationObservation,
} from "../voice-local-cancel-candidate"

const valid: CancellationObservation = {
  audioStartMs: 1000,
  detectedAtMs: 1300,
  confidence: 0.9,
  phrase: "gravitre cancel task",
  source: "local_kws",
}

describe("PR587 local KWS candidate is not an authorization bypass", () => {
  it("remains shadow-only until independent audio certification", () => {
    expect(LOCAL_KWS_SHADOW_ONLY).toBe(true)
    expect(CANCELLATION_LIMIT_MS).toBe(500)
  })
  it("records an in-budget observation without performing any cancellation", () => {
    expect(evaluateLocalCancelCandidate(valid, true)).toEqual({ status: "observed", latencyMs: 300 })
  })
  it("rejects late or invalid timestamps", () => {
    expect(evaluateLocalCancelCandidate({ ...valid, detectedAtMs: 1501 }, true)).toEqual({
      status: "rejected", reason: "too_late",
    })
    expect(evaluateLocalCancelCandidate({ ...valid, detectedAtMs: 999 }, true)).toEqual({
      status: "rejected", reason: "invalid_timing",
    })
    expect(evaluateLocalCancelCandidate({ ...valid, detectedAtMs: Number.NaN }, true)).toEqual({
      status: "rejected", reason: "invalid_timing_or_score",
    })
  })
  it("rejects inactive work and ambiguous or quoted commands", () => {
    expect(evaluateLocalCancelCandidate(valid, false)).toEqual({ status: "rejected", reason: "no_active_work" })
    for (const phrase of ["stop", "cancel", "do not cancel", "she said gravitre cancel task", "gravitre cancel task please"]) {
      expect(evaluateLocalCancelCandidate({ ...valid, phrase }, true)).toEqual({
        status: "rejected", reason: "noncanonical_phrase",
      })
    }
  })
  it("normalizes spoken phrase whitespace without widening the accepted command", () => {
    for (const phrase of ["  GRAVITRE   cancel task  ", "gravitre\t cancel\n task"]) {
      expect(evaluateLocalCancelCandidate({ ...valid, phrase }, true)).toEqual({
        status: "observed", latencyMs: 300,
      })
    }
    expect(evaluateLocalCancelCandidate({ ...valid, phrase: "don't gravitre cancel task" }, true)).toEqual({
      status: "rejected", reason: "noncanonical_phrase",
    })
  })
  it("does not accept an invalid score", () => {
    expect(evaluateLocalCancelCandidate({ ...valid, confidence: 2 }, true)).toEqual({
      status: "rejected", reason: "invalid_score",
    })
  })
})
