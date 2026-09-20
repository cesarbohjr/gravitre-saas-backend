/**
 * Creative → Product UI grammar (Phase 12).
 * Thin re-exports — interaction language only, no marketing scenes on product routes.
 */

export { GravitreEvidenceMark as EvidenceChip } from "@/components/marketing/creative/primitives/evidence-mark"
export { CREATIVE_BRAND as GRAMMAR_BRAND } from "@/components/marketing/creative/core/tokens"

/** Step / gate semantic tones aligned with creative WAITING / verified / failed. */
export const GRAMMAR_STEP_TONE = {
  pending: "muted",
  running: "info",
  waiting: "warning",
  verified: "success",
  failed: "destructive",
} as const

export type GrammarStepTone = (typeof GRAMMAR_STEP_TONE)[keyof typeof GRAMMAR_STEP_TONE]

export function grammarToneForStepStatus(
  status: string,
): keyof typeof GRAMMAR_STEP_TONE {
  switch (status) {
    case "awaiting_approval":
      return "waiting"
    case "running":
      return "running"
    case "completed":
    case "approved":
    case "verified":
      return "verified"
    case "failed":
    case "rejected":
      return "failed"
    default:
      return "pending"
  }
}
