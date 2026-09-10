/**
 * Friendly, specific agent status copy for the chat waiting bubble.
 * Maps backend progress / SSE metadata through the AI State matrix —
 * never raw codes, class names, or logger strings.
 */
import {
  sanitizeUserActivityLabel,
  SAFE_STATUS_FALLBACK,
  specificToolStatus,
} from "@/lib/ai-state-matrix"
import {
  deriveNamedProgressSteps,
  type NamedProgressStep,
  type PendingTaskLike,
} from "@/lib/chat-progress-steps"

const DIALOGUE_MODE_STATUS: Record<string, string> = {
  answer: "Composing a response",
  clarify: "Figuring out what to ask next",
  confirm: "Preparing something for your approval",
  guide: "Planning the next steps",
  recommend: "Comparing the options",
  execute: "Running the requested action",
  simulate: "Simulating the action first",
  research: "Searching your knowledge and connected tools",
  escalate: "Reviewing whether this needs a human",
  summarize: "Summarizing what we found",
}

function statusFromNamedStep(steps: NamedProgressStep[]): string | null {
  const current = steps.find((step) => step.status === "current")
  if (current?.label) return current.label
  const lastDone = [...steps].reverse().find((step) => step.status === "done")
  if (lastDone?.label) return lastDone.label
  const firstPending = steps.find((step) => step.status === "pending")
  if (firstPending?.label) return firstPending.label
  return null
}

function statusFromRawProgress(progressSteps: string[] | null | undefined): string | null {
  for (const raw of [...(progressSteps ?? [])].reverse()) {
    const text = String(raw ?? "").trim()
    if (!text || /^Completed:/i.test(text)) continue
    const label = sanitizeUserActivityLabel(text)
    if (label && label !== SAFE_STATUS_FALLBACK) return label
  }
  return null
}

export type AgentStatusInput = {
  assistantLabel?: string
  progressSteps?: string[] | null
  answerExplanation?: string | null
  userStatusLabel?: string | null
  dialogueMode?: string | null
  activeToolName?: string | null
  isStreaming?: boolean
  isBusy?: boolean
  pendingTask?: PendingTaskLike
  connectedIntegrations?: string[] | null
}

export function deriveAgentStatusLabel(input: AgentStatusInput): string {
  const suffix = (phrase: string) => {
    const cleaned = sanitizeUserActivityLabel(phrase, {
      connectors: input.connectedIntegrations,
    })
    return cleaned.endsWith("…") || cleaned.endsWith("...") ? cleaned : `${cleaned}…`
  }

  if (input.pendingTask?.status === "awaiting_confirm") {
    return suffix("Preparing something for your approval")
  }

  if (input.userStatusLabel?.trim()) {
    const fromUser = sanitizeUserActivityLabel(input.userStatusLabel, {
      connectors: input.connectedIntegrations,
    })
    if (fromUser !== SAFE_STATUS_FALLBACK) return suffix(fromUser)
  }

  const fromAnswer = sanitizeUserActivityLabel(input.answerExplanation, {
    connectors: input.connectedIntegrations,
  })
  if (input.answerExplanation?.trim() && fromAnswer !== SAFE_STATUS_FALLBACK) {
    return suffix(fromAnswer)
  }

  const fromRawProgress = statusFromRawProgress(input.progressSteps)
  if (fromRawProgress && fromRawProgress !== SAFE_STATUS_FALLBACK) {
    return suffix(fromRawProgress)
  }

  const named = deriveNamedProgressSteps(input.progressSteps, input.pendingTask)
  const fromProgress = statusFromNamedStep(named)
  if (fromProgress) return suffix(fromProgress)

  const toolLabel = specificToolStatus(input.activeToolName, input.connectedIntegrations)
  if (toolLabel) return suffix(toolLabel)

  if (input.dialogueMode && DIALOGUE_MODE_STATUS[input.dialogueMode]) {
    return suffix(DIALOGUE_MODE_STATUS[input.dialogueMode])
  }

  return suffix(SAFE_STATUS_FALLBACK.replace(/…$/, ""))
}

export function shouldHideProgressPanel(
  progressSteps?: string[] | null,
  pendingTask?: PendingTaskLike,
): boolean {
  const named = deriveNamedProgressSteps(progressSteps, pendingTask)
  return named.length < 2
}
