/**
 * Model Studio "Improve agent": pure helpers for building the request to
 * POST /api/agents/{id}/improvements and confirming results against the
 * agent's re-fetched state.
 */

export type AgentImprovementKind = "instruction" | "model" | "fine_tune" | "knowledge"

export type AgentImprovementStepStatus = "applied" | "unchanged" | "failed"

export interface AgentImprovementStep {
  kind: AgentImprovementKind
  status: AgentImprovementStepStatus
  message: string
  target: string | null
  verified: boolean
}

export interface AgentImprovementState {
  agentId: string
  name: string
  storage: "agent" | "operator"
  model: string | null
  trainedModelId: string | null
  instructions: Array<{ id: string; name?: string | null; content: string }>
  knowledgeSourceIds: string[]
  supportsKnowledge: boolean
}

export interface AgentImprovementsRequest {
  instruction?: { name?: string; content: string }
  model?: string
  trainedModelId?: string
  knowledgeSourceIds?: string[]
}

export interface AgentImprovementsResult {
  agentId: string
  steps: AgentImprovementStep[]
  appliedCount: number
  failedCount: number
  state: AgentImprovementState
}

export interface AgentImprovementSelection {
  instruction: { enabled: boolean; text: string }
  model: { enabled: boolean; value: string }
  fineTune: { enabled: boolean; id: string }
  knowledge: { enabled: boolean; ids: string[] }
}

export const EMPTY_IMPROVEMENT_SELECTION: AgentImprovementSelection = {
  instruction: { enabled: false, text: "" },
  model: { enabled: false, value: "" },
  fineTune: { enabled: false, id: "" },
  knowledge: { enabled: false, ids: [] },
}

export const MAX_IMPROVEMENT_NOTE_CHARS = 4000
export const MAX_IMPROVEMENT_KNOWLEDGE = 10

export interface AgentModelChoice {
  id: string
  label: string
  description?: string
}

/**
 * Models offered for an agent switch, taken from an app-wide list. "auto" is
 * dropped: the agent runtime treats the stored value as a literal model id.
 */
export function buildAgentModelChoices(
  options: ReadonlyArray<{ id: string; label: string; description?: string }>,
): AgentModelChoice[] {
  const seen = new Set<string>()
  const out: AgentModelChoice[] = []
  for (const option of options) {
    const id = String(option.id || "").trim()
    if (!id || id.toLowerCase() === "auto" || seen.has(id)) continue
    seen.add(id)
    out.push({ id, label: option.label || id, description: option.description })
  }
  return out
}

export type BuildImprovementResult =
  | { ok: true; body: AgentImprovementsRequest }
  | { ok: false; error: string }

/** Turn the checked improvements into a request body, or explain what is missing. */
export function buildImprovementRequest(
  selection: AgentImprovementSelection,
  opts: { supportsKnowledge?: boolean } = {},
): BuildImprovementResult {
  const body: AgentImprovementsRequest = {}

  if (selection.instruction.enabled) {
    const content = selection.instruction.text.trim()
    if (!content) return { ok: false, error: "Write the coaching note or uncheck it." }
    if (content.length > MAX_IMPROVEMENT_NOTE_CHARS) {
      return { ok: false, error: `Keep the note under ${MAX_IMPROVEMENT_NOTE_CHARS} characters.` }
    }
    body.instruction = { content }
  }

  if (selection.model.enabled) {
    const model = selection.model.value.trim()
    if (!model) return { ok: false, error: "Pick a model or uncheck it." }
    body.model = model
  }

  if (selection.fineTune.enabled) {
    const id = selection.fineTune.id.trim()
    if (!id) return { ok: false, error: "Pick a fine-tuned model or uncheck it." }
    body.trainedModelId = id
  }

  if (selection.knowledge.enabled) {
    if (opts.supportsKnowledge === false) {
      return { ok: false, error: "This agent can't take knowledge from here. Uncheck it." }
    }
    const ids = Array.from(new Set(selection.knowledge.ids.map((id) => id.trim()).filter(Boolean)))
    if (ids.length === 0) return { ok: false, error: "Pick at least one knowledge source or uncheck it." }
    if (ids.length > MAX_IMPROVEMENT_KNOWLEDGE) {
      return { ok: false, error: `Pick up to ${MAX_IMPROVEMENT_KNOWLEDGE} knowledge sources.` }
    }
    body.knowledgeSourceIds = ids
  }

  if (Object.keys(body).length === 0) return { ok: false, error: "Choose at least one improvement." }
  return { ok: true, body }
}

/** Is this step's change visible in the agent's freshly fetched state? */
export function isStepConfirmed(
  step: AgentImprovementStep,
  state: AgentImprovementState | null | undefined,
  request: AgentImprovementsRequest,
): boolean {
  if (!state || step.status === "failed") return false
  switch (step.kind) {
    case "model":
      return Boolean(step.target) && state.model === step.target
    case "fine_tune":
      return Boolean(step.target) && state.trainedModelId === step.target
    case "knowledge":
      return Boolean(step.target) && state.knowledgeSourceIds.includes(String(step.target))
    case "instruction": {
      const content = request.instruction?.content.trim()
      if (!content) return false
      return state.instructions.some((item) => String(item.content || "").includes(content))
    }
    default:
      return false
  }
}

export const IMPROVEMENT_KIND_LABEL: Record<AgentImprovementKind, string> = {
  instruction: "Coaching note",
  model: "Model",
  fine_tune: "Fine-tuned model",
  knowledge: "Knowledge",
}

export type StepOutcome = "confirmed" | "not_confirmed" | "failed"

/** One line per step for the result list. */
export function summarizeStep(
  step: AgentImprovementStep,
  confirmed: boolean,
  names: { models?: Record<string, string>; fineTunes?: Record<string, string>; sources?: Record<string, string> } = {},
): { label: string; outcome: StepOutcome; detail: string } {
  const base = IMPROVEMENT_KIND_LABEL[step.kind]
  const target = step.target ?? ""
  const targetName =
    step.kind === "model"
      ? names.models?.[target] ?? target
      : step.kind === "fine_tune"
        ? names.fineTunes?.[target] ?? target
        : step.kind === "knowledge"
          ? names.sources?.[target] ?? target
          : ""
  const label = targetName ? `${base}: ${targetName}` : base
  if (step.status === "failed") return { label, outcome: "failed", detail: step.message || "Not applied." }
  if (!confirmed) return { label, outcome: "not_confirmed", detail: "Saved, but not seen on the agent yet." }
  return {
    label,
    outcome: "confirmed",
    detail: step.status === "unchanged" ? "Already in place." : "Applied and confirmed.",
  }
}
