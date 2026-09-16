/** Machine quality flags → customer-facing copy (I4 / spec Appendix A). */
const QUALITY_COPY: Record<string, string> = {
  INSUFFICIENT_DATA: "Not enough verified data yet",
  NOT_CONFIGURED: "Not set up yet",
  UNSCOPED_PREDICTION: "This signal needs a connected source",
  NO_OUTCOME_ATTRIBUTION: "No outcome path is attributed yet",
  NO_BUSINESS_LEARNING_YET: "No validated business learning in this period",
  PARTIAL_SNAPSHOT: "Some intelligence sources are still loading",
  DEGRADED_SOURCES: "Some sources unavailable",
  SOURCE_UNAVAILABLE: "A data source is temporarily unavailable",
  INSUFFICIENT_EVIDENCE: "Not enough verified evidence yet",
}

export function qualityFlagToCopy(flag: string): string {
  const key = flag.trim().toUpperCase()
  if (QUALITY_COPY[key]) return QUALITY_COPY[key]!
  return flag
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatQualityFlagsHuman(flags: string[]): string[] {
  return [...new Set(flags.map(qualityFlagToCopy))]
}
