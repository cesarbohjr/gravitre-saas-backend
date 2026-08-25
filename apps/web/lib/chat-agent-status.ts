/**
 * Friendly, Claude-style agent status copy for the chat waiting bubble.
 * Maps backend progress / SSE metadata to user-facing activity text — never
 * raw codes, vendor names in bulk, or internal routing labels.
 */
import {
  deriveNamedProgressSteps,
  type NamedProgressStep,
  type PendingTaskLike,
} from "@/lib/chat-progress-steps"
import { mapToolNameToModeLabel } from "@/components/gravitre/assistant/dialogue-mode-chip"

const INTERNAL_ANSWER_PATTERN =
  /^(routing classified|reAct write gated|orphan_plan|governed connector|unified turn|tier_|engine_)/i

const RAW_CODE_PATTERN =
  /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g

/** Backend context-phase labels → friendly activity copy. */
const PROGRESS_LABEL_MAP: Record<string, string> = {
  "classifying request": "Understanding your request",
  "checking connected systems and knowledge": "Checking your connected systems",
  "loading memory and knowledge": "Reviewing context and memory",
  "analyzing your request": "Understanding your request",
  "reviewing connected systems and knowledge": "Checking your connected systems",
}

const DIALOGUE_MODE_STATUS: Record<string, string> = {
  answer: "Composing a response",
  clarify: "Thinking through what to ask",
  confirm: "Preparing something for your approval",
  guide: "Planning next steps",
  recommend: "Analyzing options",
  execute: "Executing",
  simulate: "Simulating",
  research: "Researching",
  escalate: "Reviewing escalation options",
  summarize: "Summarizing",
}

function normalizeKey(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ")
}

function friendlyProgressLabel(label: string): string {
  const key = normalizeKey(label.replace(/\([^)]*\)/g, "").trim())
  if (PROGRESS_LABEL_MAP[key]) return PROGRESS_LABEL_MAP[key]
  if (/^checking .+/i.test(label)) return "Checking your connected systems"
  if (/^loading .+/i.test(label)) return "Reviewing context and memory"
  if (/^running:/i.test(label)) return friendlyProgressLabel(label.replace(/^running:\s*/i, ""))
  if (/^classifying/i.test(label)) return "Understanding your request"
  if (/search/i.test(label)) return "Searching"
  if (/read/i.test(label)) return "Reading"
  if (/writ/i.test(label)) return "Writing"
  if (/execut/i.test(label)) return "Executing"
  if (/analy/i.test(label)) return "Analyzing"
  return label.replace(/\([^)]*\)/g, "").trim() || "Working on it"
}

function stripInternalAnswer(text: string): string | null {
  const trimmed = text.trim()
  if (!trimmed || INTERNAL_ANSWER_PATTERN.test(trimmed)) return null
  if (/^write_approval_required$/i.test(trimmed)) return null
  if (RAW_CODE_PATTERN.test(trimmed) && trimmed.length < 80 && trimmed.includes("_")) {
    return null
  }
  return trimmed.replace(/^Running:\s*/i, "").replace(/…+$/, "").trim() || null
}

function statusFromNamedStep(steps: NamedProgressStep[]): string | null {
  const current = steps.find((step) => step.status === "current")
  if (current?.label) return friendlyProgressLabel(current.label)
  const lastDone = [...steps].reverse().find((step) => step.status === "done")
  if (lastDone?.label) return friendlyProgressLabel(lastDone.label)
  const firstPending = steps.find((step) => step.status === "pending")
  if (firstPending?.label) return friendlyProgressLabel(firstPending.label)
  return null
}

/** Context-phase SSE strings have no Running:/Completed: prefix — read them directly. */
function statusFromRawProgress(progressSteps: string[] | null | undefined): string | null {
  for (const raw of [...(progressSteps ?? [])].reverse()) {
    const text = String(raw ?? "").trim()
    if (!text || /^Completed:/i.test(text)) continue
    const label = text
      .replace(/^Running:\s*/i, "")
      .replace(/^Step \d+\/\d+:\s*/i, "")
      .trim()
    if (label) return friendlyProgressLabel(label)
  }
  return null
}

export type AgentStatusInput = {
  assistantLabel?: string
  progressSteps?: string[] | null
  answerExplanation?: string | null
  dialogueMode?: string | null
  activeToolName?: string | null
  isStreaming?: boolean
  isBusy?: boolean
  pendingTask?: PendingTaskLike
}

export function deriveAgentStatusLabel(input: AgentStatusInput): string {
  const label = (input.assistantLabel || "Gravitre").trim()
  const suffix = (phrase: string) => `${phrase}…`

  if (input.pendingTask?.status === "awaiting_confirm") {
    return suffix("Preparing something for your approval")
  }

  const fromAnswer = stripInternalAnswer(String(input.answerExplanation || ""))
  if (fromAnswer) {
    const lower = fromAnswer.toLowerCase()
    if (lower.includes("approval")) return suffix("Preparing something for your approval")
    if (lower.includes("search") || lower.includes("retriev")) return suffix("Searching")
    if (lower.includes("analy")) return suffix("Analyzing")
    if (lower.includes("execut") || lower.includes("running")) return suffix("Executing")
    if (lower.includes("read") || lower.includes("review")) return suffix("Reading")
    if (lower.includes("writ")) return suffix("Writing")
    return suffix(fromAnswer.charAt(0).toUpperCase() + fromAnswer.slice(1))
  }

  const fromRawProgress = statusFromRawProgress(input.progressSteps)
  if (fromRawProgress) return suffix(fromRawProgress)

  const named = deriveNamedProgressSteps(input.progressSteps, input.pendingTask)
  const fromProgress = statusFromNamedStep(named)
  if (fromProgress) return suffix(fromProgress)

  const toolLabel = mapToolNameToModeLabel(input.activeToolName)
  if (toolLabel) return suffix(toolLabel)

  if (input.dialogueMode && DIALOGUE_MODE_STATUS[input.dialogueMode]) {
    return suffix(DIALOGUE_MODE_STATUS[input.dialogueMode])
  }

  if (input.isStreaming || input.isBusy) {
    return suffix(`${label} is thinking`)
  }

  return suffix(`${label} is thinking`)
}

export function shouldHideProgressPanel(progressSteps?: string[] | null): boolean {
  const steps = progressSteps ?? []
  if (steps.length === 0) return true
  // Context-phase steps are for the agent bubble only — not a separate panel.
  return steps.every((step) => !/^(Running:|Completed:|Step \d+\/\d+:)/i.test(String(step).trim()))
}
