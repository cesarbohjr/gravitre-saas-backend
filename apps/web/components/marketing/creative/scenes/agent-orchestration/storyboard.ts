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
