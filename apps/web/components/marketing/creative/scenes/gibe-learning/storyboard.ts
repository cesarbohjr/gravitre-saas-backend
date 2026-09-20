/**
 * Phase 8 — GIBE Learning Loop storyboard (illustrative, deterministic).
 * ACTION → OBSERVE → EVALUATE → RECOMMEND (advisory) → APPROVE → RETAIN
 */

export const ILLUSTRATIVE_CONTEXT =
  "GIBE observes approved work, evaluates what worked, recommends a preferred path — then a human approves before anything changes."

export const LOOP_STAGES = [
  { id: "action", label: "Action" },
  { id: "observe", label: "Observe" },
  { id: "evaluate", label: "Evaluate" },
  { id: "recommend", label: "Recommend" },
  { id: "approve", label: "Approve" },
  { id: "retain", label: "Retain" },
] as const

export type GibePhase =
  | "quiet"
  | "action"
  | "observe"
  | "evaluate"
  | "recommend"
  | "approve"
  | "retain"
  | "honest"

export const PHASE_ORDER: GibePhase[] = [
  "quiet",
  "action",
  "observe",
  "evaluate",
  "recommend",
  "approve",
  "retain",
  "honest",
]

export const PHASE_CAPTION: Record<GibePhase, string> = {
  quiet: "GIBE at rest — no learning loop open.",
  action: "An action runs through your connected stack.",
  observe: "GIBE observes what happened after the action.",
  evaluate: "Evaluate which path produced a useful outcome.",
  recommend: "Recommend a preferred path — advisory only.",
  approve: "Human approval required before the recommendation sticks.",
  retain: "Approved preference is retained for the next similar intent.",
  honest: "Illustrative loop only — not auto policy rewrite.",
}

export function nextPhase(phase: GibePhase): GibePhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isGibePhase(value: string | null | undefined): value is GibePhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

export function parseGibeStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): GibePhase | null {
  if (!isGibePhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

/** Stages lit through the current phase (inclusive). */
export function activeStageIds(phase: GibePhase): string[] {
  switch (phase) {
    case "quiet":
      return []
    case "action":
      return ["action"]
    case "observe":
      return ["action", "observe"]
    case "evaluate":
      return ["action", "observe", "evaluate"]
    case "recommend":
      return ["action", "observe", "evaluate", "recommend"]
    case "approve":
      return ["action", "observe", "evaluate", "recommend", "approve"]
    case "retain":
    case "honest":
      return ["action", "observe", "evaluate", "recommend", "approve", "retain"]
    default:
      return []
  }
}

export function isAdvisory(phase: GibePhase): boolean {
  return phase === "recommend"
}

export function isWaiting(phase: GibePhase): boolean {
  return phase === "approve"
}

export function showRetain(phase: GibePhase): boolean {
  return phase === "retain" || phase === "honest"
}

/** Same preference path continues through approve → retain (no restart). */
export const GIBE_PREFERENCE_PATH_ID = "path-gibe-prefer"
