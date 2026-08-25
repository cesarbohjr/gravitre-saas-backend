/** Shared dialogue / tool activity labels for chat status chrome (no React). */

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
  if (!toolName) return null
  const normalized = toolName.toLowerCase()
  if (normalized.includes("knowledge") || normalized.includes("search")) return "Retrieving"
  if (normalized.includes("connector")) return "Checking connectors"
  if (normalized.includes("simulation") || normalized.includes("simulate")) return "Simulating"
  if (normalized.includes("approval")) return "Awaiting approval"
  return "Analyzing"
}
