/**
 * PR587 local cancellation keyword candidate — shadow-only until real-audio
 * false-positive and microphone-to-write-fence certification passes.
 *
 * A detector implementation (e.g. a licensed on-device KWS engine) supplies
 * positive events. This module never interprets raw PCM as a cancellation and
 * never dispatches commands or approves writes. It deliberately requires the
 * full phrase event from the acoustic engine, not an interim STT word.
 */
export type CancellationObservation = {
  audioStartMs: number
  detectedAtMs: number
  confidence: number
  phrase: string
  source: "local_kws"
}
export type CancellationVerdict =
  | { status: "observed"; latencyMs: number }
  | { status: "rejected"; reason: string }

export const CANCELLATION_LIMIT_MS = 500
export const LOCAL_KWS_SHADOW_ONLY = true

// Only a distinct, trained command may be assessed; bare "stop" is ambiguous.
// An exact normalized match is necessary but not sufficient for certification.
const CANDIDATE_PHRASE = "gravitre cancel task"

export function evaluateLocalCancelCandidate(
  observation: CancellationObservation,
  workActive: boolean,
): CancellationVerdict {
  if (!workActive) return { status: "rejected", reason: "no_active_work" }
  if (observation.source !== "local_kws") return { status: "rejected", reason: "untrusted_source" }
  if (observation.phrase.trim().toLowerCase().replace(/\s+/g, " ") !== CANDIDATE_PHRASE)
    return { status: "rejected", reason: "noncanonical_phrase" }
  if (![observation.audioStartMs, observation.detectedAtMs, observation.confidence].every(Number.isFinite))
    return { status: "rejected", reason: "invalid_timing_or_score" }
  if (observation.confidence < 0 || observation.confidence > 1)
    return { status: "rejected", reason: "invalid_score" }
  const latencyMs = observation.detectedAtMs - observation.audioStartMs
  if (latencyMs < 0) return { status: "rejected", reason: "invalid_timing" }
  if (latencyMs > CANCELLATION_LIMIT_MS) return { status: "rejected", reason: "too_late" }
  // No runtime side effects: a shadow observation cannot call cancel_turn_work.
  return { status: "observed", latencyMs }
}
