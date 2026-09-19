/**
 * Pilot 2 — Task Decomposition Field storyboard (illustrative, deterministic).
 */

export const ILLUSTRATIVE_REQUEST = "Find at-risk customers and prepare the right follow-up."

export const PLAN_CHIPS = [
  "Identify accounts",
  "Analyze signals",
  "Check CRM context",
  "Determine response",
  "Prepare action",
  "Verify",
] as const

export const AGENT_ROLES = [
  { id: "research", label: "Research" },
  { id: "analysis", label: "Analysis" },
  { id: "support", label: "Support" },
  { id: "ops", label: "Operations" },
] as const

export const TOOLS = ["CRM context", "Signals", "Messaging"] as const

export type OrchestrationPhase =
  | "quiet"
  | "intent"
  | "understand"
  | "plan"
  | "delegate"
  | "tools"
  | "parallel"
  | "waiting"
  | "verify"
  | "outcome"
  | "learned"
  | "failure"

export const PHASE_ORDER: OrchestrationPhase[] = [
  "quiet",
  "intent",
  "understand",
  "plan",
  "delegate",
  "tools",
  "parallel",
  "waiting",
  "verify",
  "outcome",
  "learned",
]

export const PHASE_CAPTION: Record<OrchestrationPhase, string> = {
  quiet: "System at rest.",
  intent: "A business request enters Gravitre.",
  understand: "Gravitre understands the request — topology reorganizes.",
  plan: "The request becomes an ordered plan.",
  delegate: "Relevant capabilities receive only their work.",
  tools: "Capabilities reach the systems they need.",
  parallel: "Two paths execute at the same time.",
  waiting: "Needs approval before a write. Governance pauses this path.",
  verify: "Evidence attaches to the result.",
  outcome: "Many actions resolve into one outcome.",
  learned: "A relationship remains. Learning stays advisory — not an automatic policy rewrite.",
  failure: "Messaging failed at send. Prior research stands. The dependent follow-up is blocked.",
}

/** Illustrative write-path id — approval must continue this same path (no restart). */
export const GOVERNED_WRITE_PATH_ID = "path-write-follow-up"

export function nextPhase(phase: OrchestrationPhase, mode: "success" | "failure"): OrchestrationPhase {
  if (mode === "failure" && phase === "parallel") return "failure"
  if (phase === "failure") return "quiet"
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function phaseAtLeast(current: OrchestrationPhase, target: OrchestrationPhase): boolean {
  const order = [...PHASE_ORDER, "failure"] as OrchestrationPhase[]
  return order.indexOf(current) >= order.indexOf(target)
}

export function isOrchestrationPhase(value: string | null | undefined): value is OrchestrationPhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value) || value === "failure"
}

/**
 * Parse `?creativeState=` for deterministic review frames.
 * Allowed on localhost / 127.0.0.1 only (dev + local Playwright) — not public prod freeze.
 */
export function parseCreativeStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): OrchestrationPhase | null {
  if (!isOrchestrationPhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

/** Active path ids for a phase — failure must not mark every path error. */
export function pathStatesForPhase(
  phase: OrchestrationPhase,
): Record<"research" | "write", "active" | "waiting" | "success" | "blocked" | "error" | "idle"> {
  switch (phase) {
    case "parallel":
      return { research: "active", write: "active" }
    case "waiting":
      return { research: "success", write: "waiting" }
    case "verify":
    case "outcome":
    case "learned":
      return { research: "success", write: "success" }
    case "failure":
      return { research: "success", write: "error" }
    default:
      return { research: "idle", write: "idle" }
  }
}

/** Path continuity: waiting → verify keeps the same governed write path id. */
export function activePathId(phase: OrchestrationPhase): string | null {
  if (phase === "waiting" || phase === "verify" || phase === "outcome" || phase === "learned") {
    return GOVERNED_WRITE_PATH_ID
  }
  if (phase === "failure") return GOVERNED_WRITE_PATH_ID
  if (phase === "parallel" || phase === "tools") return GOVERNED_WRITE_PATH_ID
  return null
}
