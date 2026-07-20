import { NextResponse } from "next/server"
import {
  EMPTY_LIVE_INTEL,
  buildMemoryLearningClaim,
  buildOperationalSuccessClaim,
  buildQueryClusterClaim,
  buildRetrievalRankerClaim,
  type LiveIntelSnapshot,
} from "@/lib/marketing-intelligence-truth"

/**
 * Public marketing honesty feed (Module C).
 *
 * Returns claim objects built by the same formatters the homepage uses.
 * Does not invent TRAINED badges or confidence percentages.
 *
 * When a future platform-wide / anonymous aggregate exists, merge real fields
 * into `live` here — formatters already refuse fabricated scores.
 */
export async function GET() {
  const live: LiveIntelSnapshot = { ...EMPTY_LIVE_INTEL }

  // Optional: if MARKETING_LIVE_INTEL_JSON is set to a validated snapshot, use it.
  // Never accept unvalidated marketing copy with hardcoded confidence.
  const raw = process.env.MARKETING_LIVE_INTEL_JSON
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as LiveIntelSnapshot
      Object.assign(live, parsed)
    } catch {
      // ignore invalid env — keep empty honest defaults
    }
  }

  return NextResponse.json({
    source: "marketing-intelligence-truth",
    moduleC: true,
    live,
    claims: {
      retrievalRanker: buildRetrievalRankerClaim(live),
      queryClusters: buildQueryClusterClaim(live),
      operationalSuccess: buildOperationalSuccessClaim(live),
      memoryLearning: buildMemoryLearningClaim(live),
    },
  })
}
