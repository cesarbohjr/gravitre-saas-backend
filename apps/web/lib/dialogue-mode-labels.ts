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

export function mapToolNameToModeLabel(toolName?: string | null): string | null {
  return specificToolStatus(toolName)
}
