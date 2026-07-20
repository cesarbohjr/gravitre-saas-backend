/**
 * Marketing intelligence claims — Module C / STA-331 honesty by construction.
 *
 * Never invent a precise confidence or TRAINED badge for marketing mocks.
 * If live org/platform data is supplied and meets Module C rules, show it;
 * otherwise use directional language (same estimate / data-gate / heuristic taxonomy).
 */
import {
  CONFIDENCE_ESTIMATE_METHODOLOGY,
  ESTIMATED_CONFIDENCE_LABEL,
  OPERATIONAL_SUCCESS_RATE_LABEL,
} from "@/lib/outcome-labels"

export type MarketingClaimProvenance =
  | "computed"
  | "estimate"
  | "heuristic"
  | "data_gate"
  | "operational"
  | "directional"

export type LiveIntelSnapshot = {
  confidence?: number | null
  confidenceIsEstimate?: boolean | null
  liveInferencePath?: string | null
  artifactLoaded?: boolean | null
  sampleSize?: number | null
  /** Min samples before a hard confidence % may be shown (retrieval LTR gate = 100). */
  minSamplesForScore?: number | null
  queryClusterCount?: number | null
  knowledgeGapCount?: number | null
  /** Operational success rate 0–1 from real run telemetry only. */
  operationalSuccessRate?: number | null
  operationalRunCount?: number | null
}

export type MarketingIntelClaim = {
  eyebrow: string
  primary: string
  provenance: MarketingClaimProvenance
  /** Optional secondary line (methodology / gate note). */
  note?: string
}

const RETRIEVAL_MIN_SAMPLES = 100

/** Format a 0–1 confidence only when Module C would allow a non-estimate live score. */
export function formatLiveConfidencePercent(live?: LiveIntelSnapshot | null): string | null {
  if (!live) return null
  if (!live.artifactLoaded) return null
  if (live.confidenceIsEstimate) return null
  if (live.confidence == null || Number.isNaN(live.confidence)) return null
  const min = live.minSamplesForScore ?? RETRIEVAL_MIN_SAMPLES
  if (live.sampleSize != null && live.sampleSize < min) return null
  const pct = Math.round(Math.max(0, Math.min(1, live.confidence)) * 100)
  return `${pct}%`
}

export function buildRetrievalRankerClaim(live?: LiveIntelSnapshot | null): MarketingIntelClaim {
  const livePct = formatLiveConfidencePercent(live)
  if (livePct && live?.liveInferencePath === "loaded_model_artifact") {
    return {
      eyebrow: "Retrieval ranker",
      primary: `Live model · ${livePct} confidence`,
      provenance: "computed",
      note: "Computed from a loaded org artifact — not a catalog TRAINED label alone.",
    }
  }
  if (
    live?.liveInferencePath === "data_gate" ||
    (live?.sampleSize != null && live.sampleSize < (live.minSamplesForScore ?? RETRIEVAL_MIN_SAMPLES))
  ) {
    return {
      eyebrow: "Retrieval ranker",
      primary: "Data gate · waits for enough org outcomes before training",
      provenance: "data_gate",
      note: CONFIDENCE_ESTIMATE_METHODOLOGY,
    }
  }
  return {
    eyebrow: "Retrieval ranker",
    primary: "Heuristic baseline until your org’s outcomes season a live model",
    provenance: "heuristic",
    note: `${ESTIMATED_CONFIDENCE_LABEL} only — never a fabricated TRAINED percentage.`,
  }
}

export function buildQueryClusterClaim(live?: LiveIntelSnapshot | null): MarketingIntelClaim {
  const clusters = live?.queryClusterCount
  const gaps = live?.knowledgeGapCount
  if (
    typeof clusters === "number" &&
    clusters >= 0 &&
    typeof gaps === "number" &&
    gaps >= 0 &&
    (live?.sampleSize == null || live.sampleSize > 0)
  ) {
    return {
      eyebrow: "Query clusters",
      primary: `${clusters} themes · ${gaps} knowledge gaps (from your org)`,
      provenance: "operational",
      note: "Counts from org learning signals — not illustrative mock data.",
    }
  }
  return {
    eyebrow: "Query clusters",
    primary: "Gravitree learns themes and gaps from your verified org queries",
    provenance: "directional",
    note: "Hard theme/gap counts appear only after real org clustering data exists.",
  }
}

export function buildOperationalSuccessClaim(live?: LiveIntelSnapshot | null): MarketingIntelClaim {
  const rate = live?.operationalSuccessRate
  const runs = live?.operationalRunCount ?? 0
  if (typeof rate === "number" && !Number.isNaN(rate) && runs > 0) {
    const pct = Math.round(Math.max(0, Math.min(1, rate)) * 100)
    return {
      eyebrow: OPERATIONAL_SUCCESS_RATE_LABEL,
      primary: `${pct}%`,
      provenance: "operational",
      note: `From ${runs} recorded runs — operational telemetry, not a marketing estimate.`,
    }
  }
  return {
    eyebrow: OPERATIONAL_SUCCESS_RATE_LABEL,
    primary: "Tracked live in your workspace",
    provenance: "directional",
    note: "No fabricated success percentage on the public site.",
  }
}

export function buildMemoryLearningClaim(live?: LiveIntelSnapshot | null): MarketingIntelClaim {
  const livePct = formatLiveConfidencePercent(live)
  if (livePct) {
    return {
      eyebrow: "Org memory",
      primary: `Live confidence ${livePct}`,
      provenance: live?.confidenceIsEstimate ? "estimate" : "computed",
      note: live?.confidenceIsEstimate
        ? ESTIMATED_CONFIDENCE_LABEL
        : "From a loaded model artifact / outcome computation.",
    }
  }
  return {
    eyebrow: "Org memory",
    primary: "Gravitree learns from every approved action",
    provenance: "directional",
    note: "Precise memory confidence appears in-product once your org has real signals — never invented for marketing.",
  }
}

/** Default public-site snapshot: no live numbers (honest empty). */
export const EMPTY_LIVE_INTEL: LiveIntelSnapshot = {
  confidence: null,
  confidenceIsEstimate: true,
  liveInferencePath: "heuristic",
  artifactLoaded: false,
  sampleSize: 0,
  queryClusterCount: null,
  knowledgeGapCount: null,
  operationalSuccessRate: null,
  operationalRunCount: 0,
}
