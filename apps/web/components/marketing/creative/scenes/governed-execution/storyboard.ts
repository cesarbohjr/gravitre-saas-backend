/**
 * Phase 7 — Governed Execution storyboard (illustrative, deterministic).
 * POLICY → RISK → APPROVAL → EXECUTE → EVIDENCE
 */

export const ILLUSTRATIVE_CONTEXT =
  "A write reaches your systems only after policy, risk, and human approval — then evidence remains."

export const GATE_STAGES = [
  { id: "policy", label: "Policy" },
  { id: "risk", label: "Risk" },
  { id: "approval", label: "Approval" },
  { id: "execute", label: "Execute" },
  { id: "evidence", label: "Evidence" },
] as const

export type GovernancePhase =
  | "quiet"
  | "policy"
  | "risk"
  | "approval"
  | "execute"
  | "evidence"
  | "trail"
  | "honest"

export const PHASE_ORDER: GovernancePhase[] = [
  "quiet",
  "policy",
  "risk",
  "approval",
  "execute",
  "evidence",
  "trail",
  "honest",
]

export const PHASE_CAPTION: Record<GovernancePhase, string> = {
  quiet: "Governance at rest — no write path open.",
  policy: "Policy checks the proposed action.",
  risk: "Risk review scores what could go wrong.",
  approval: "Human approval required before the write. Gate paused.",
  execute: "After approval, the same path executes — no restart.",
  evidence: "Evidence attaches to the executed write.",
  trail: "The audit trail remains after the gate closes.",
  honest: "Illustrative path only — not a live compliance certification.",
}

export function nextPhase(phase: GovernancePhase): GovernancePhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isGovernancePhase(value: string | null | undefined): value is GovernancePhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

export function parseGovStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): GovernancePhase | null {
  if (!isGovernancePhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

/** Stages lit through the current phase (inclusive). */
export function activeStageIds(phase: GovernancePhase): string[] {
  switch (phase) {
    case "quiet":
      return []
    case "policy":
      return ["policy"]
    case "risk":
      return ["policy", "risk"]
    case "approval":
      return ["policy", "risk", "approval"]
    case "execute":
      return ["policy", "risk", "approval", "execute"]
    case "evidence":
    case "trail":
    case "honest":
      return ["policy", "risk", "approval", "execute", "evidence"]
    default:
      return []
  }
}

export function isWaiting(phase: GovernancePhase): boolean {
  return phase === "approval"
}

export function showEvidence(phase: GovernancePhase): boolean {
  return ["evidence", "trail", "honest"].includes(phase)
}

export function showTrail(phase: GovernancePhase): boolean {
  return ["trail", "honest"].includes(phase)
}

/** Approval continues the same path id (no restart). */
export const GOVERNED_WRITE_PATH_ID = "path-gov-write"
