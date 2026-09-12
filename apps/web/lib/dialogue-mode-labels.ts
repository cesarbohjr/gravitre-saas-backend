/** Shared dialogue / tool activity labels for chat status chrome (no React). */

import { specificToolStatus } from "@/lib/ai-state-matrix"

export const DIALOGUE_MODE_LABELS: Record<string, string> = {
  answer: "Answering",
  clarify: "Clarifying",
  confirm: "Awaiting approval",
  guide: "Planning",
  recommend: "Analyzing",
  execute: "Executing",
  simulate: "Simulating",
  research: "Retrieving",
  escalate: "Escalating",
  summarize: "Summarizing",
}

/**
 * Modes whose label describes a durable property of the finished turn rather
 * than work still under way.
 *
 * Every other label above is present-progressive — "Answering", "Analyzing",
 * "Retrieving". Those are only true while the turn is in flight. Left on a
 * completed message they claim the system is still working when it has already
 * finished, which is the defect reported from a live screenshot: an "Answering"
 * chip sitting above the finished reply "Understood."
 *
 * `confirm` / `awaiting_approval` are different in kind. "Awaiting approval"
 * remains true after the turn ends — it describes a real, outstanding state the
 * user still has to act on — so it must survive.
 */
export const DURABLE_DIALOGUE_MODES: ReadonlySet<string> = new Set([
  "confirm",
  "awaiting_approval",
])

/**
 * Whether the dialogue-mode chip should render for an assistant message.
 *
 * Pure so the rule can be tested without mounting the whole transcript.
 */
export function shouldShowDialogueModeChip(input: {
  /** Only the newest assistant turn carries live turn state. */
  isLastAssistant: boolean
  dialogueMode?: string | null
  /** Streaming, or the agent is still working on this turn. */
  turnInFlight: boolean
  /** The inline thinking row is already showing this turn's status. */
  showInlineStatus: boolean
}): boolean {
  const { isLastAssistant, dialogueMode, turnInFlight, showInlineStatus } = input
  if (!isLastAssistant || !dialogueMode) return false
  // `clarify` renders as a ClarificationMessage instead, so it never chips.
  if (dialogueMode === "clarify") return false
  // Don't stack two status affordances on one turn.
  if (showInlineStatus) return false
  if (turnInFlight) return true
  return DURABLE_DIALOGUE_MODES.has(dialogueMode)
}

export function mapToolNameToModeLabel(toolName?: string | null): string | null {
  return specificToolStatus(toolName)
}
