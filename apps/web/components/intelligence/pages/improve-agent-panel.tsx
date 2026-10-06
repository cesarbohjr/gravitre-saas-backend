"use client"

/**
 * Model Studio "Improve agent": pick an agent, choose improvements, apply them
 * through POST /api/agents/{id}/improvements, then re-fetch the agent to confirm.
 */
import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { MODEL_OPTIONS } from "@/components/gravitre/assistant/assistant-model-selector"
import { agentImprovementsApi, agentsApi, sourcesApi, trainingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  EMPTY_IMPROVEMENT_SELECTION,
  MAX_IMPROVEMENT_KNOWLEDGE,
  MAX_IMPROVEMENT_NOTE_CHARS,
  buildAgentModelChoices,
  buildImprovementRequest,
  isStepConfirmed,
  summarizeStep,
  type AgentImprovementSelection,
  type AgentImprovementsRequest,
  type AgentImprovementsResult,
} from "@/lib/intelligence/agent-improvements"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

const FIELD_CLASS =
  "min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)] disabled:opacity-60"

function ImprovementRow({
  id,
  label,
  hint,
  checked,
  disabled,
  onCheckedChange,
  children,
}: {
  id: string
  label: string
  hint: string
  checked: boolean
  disabled?: boolean
  onCheckedChange: (checked: boolean) => void
  children?: React.ReactNode
}) {
  return (
    <li className="space-y-2 px-3 py-3">
      <div className="flex items-start gap-3">
        <Checkbox
          id={id}
          checked={checked}
          disabled={disabled}
          onCheckedChange={(value) => onCheckedChange(value === true)}
          className="mt-0.5"
        />
        <label htmlFor={id} className={cn("min-w-0 flex-1", disabled && "opacity-60")}>
          <span className="block text-sm font-medium text-foreground">{label}</span>
          <span className={cn(TYPE.meta, "block")}>{hint}</span>
        </label>
      </div>
      {checked && children ? <div className="pl-7">{children}</div> : null}
    </li>
  )
}

export function ImproveAgentPanel({
  enabled,
  onPendingChange,
}: {
  enabled: boolean
  onPendingChange?: (pending: boolean) => void
}) {
  const applyLock = useRef(false)
  const [agentId, setAgentId] = useState("")
  const [selection, setSelection] = useState<AgentImprovementSelection>(EMPTY_IMPROVEMENT_SELECTION)
  const [applying, setApplying] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [result, setResult] = useState<{ request: AgentImprovementsRequest; data: AgentImprovementsResult } | null>(null)

  useEffect(() => {
    onPendingChange?.(applying)
  }, [applying, onPendingChange])
  useEffect(() => () => onPendingChange?.(false), [onPendingChange])

  const { data: agentsData, error: agentsError, isLoading: agentsLoading, mutate: mutateAgents } = useSWR(
    enabled ? "improve-agent-agents" : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )
  const {
    data: agentState,
    error: stateError,
    isLoading: stateLoading,
    mutate: mutateState,
  } = useSWR(
    enabled && agentId ? ["agent-improvement-state", agentId] : null,
    () => agentImprovementsApi.getState(agentId),
    { revalidateOnFocus: false },
  )
  const { data: fineTunesData, error: fineTunesError } = useSWR(
    enabled ? "improve-agent-fine-tunes" : null,
    () => trainingApi.listFineTunedModels(),
    { revalidateOnFocus: false },
  )
  const { data: sourcesData, error: sourcesError } = useSWR(
    enabled ? "improve-agent-knowledge-sources" : null,
    () => sourcesApi.list(),
    { revalidateOnFocus: false },
  )

  const agents = useMemo(() => agentsData?.agents ?? [], [agentsData])
  const modelChoices = useMemo(() => buildAgentModelChoices(MODEL_OPTIONS), [])
  const fineTunes = useMemo(() => fineTunesData?.models ?? [], [fineTunesData])
  const sources = useMemo(() => sourcesData?.sources ?? [], [sourcesData])
  const supportsKnowledge = agentState?.supportsKnowledge !== false
  const selectedAgent = agents.find((agent) => agent.id === agentId)

  const names = useMemo(
    () => ({
      models: Object.fromEntries(modelChoices.map((m) => [m.id, m.label])),
      fineTunes: Object.fromEntries(fineTunes.map((m) => [m.id, m.name || m.id])),
      sources: Object.fromEntries(sources.map((s) => [s.id, s.name || s.id])),
    }),
    [modelChoices, fineTunes, sources],
  )
  const currentModelLabel = agentState?.model ? names.models[agentState.model] ?? agentState.model : "Default"
  const currentFineTuneLabel = agentState?.trainedModelId
    ? names.fineTunes[agentState.trainedModelId] ?? agentState.trainedModelId
    : "None"

  function update(patch: Partial<AgentImprovementSelection>) {
    setSelection((prev) => ({ ...prev, ...patch }))
    setFormError(null)
  }

  function chooseAgent(id: string) {
    setAgentId(id)
    setSelection(EMPTY_IMPROVEMENT_SELECTION)
    setResult(null)
    setFormError(null)
    setApplyError(null)
  }

  async function apply() {
    if (applyLock.current || !agentId) return
    const built = buildImprovementRequest(selection, { supportsKnowledge })
    if (!built.ok) {
      setFormError(built.error)
      return
    }
    applyLock.current = true
    setApplying(true)
    setApplyError(null)
    setResult(null)
    try {
      const data = await agentImprovementsApi.apply(agentId, built.body)
      // Re-fetch the agent so confirmation reflects what is stored now.
      const fresh = await mutateState().catch(() => undefined)
      setResult({ request: built.body, data: fresh ? { ...data, state: fresh } : data })
      void mutateAgents()
      if (data.failedCount === 0) setSelection(EMPTY_IMPROVEMENT_SELECTION)
    } catch (error) {
      setApplyError(error instanceof Error ? error.message : "Could not apply improvements.")
    } finally {
      applyLock.current = false
      setApplying(false)
    }
  }

  if (agentsError) {
    return (
      <WorkSectionErrorCard
        title="Could not load agents"
        message="Try again to pick an agent."
        onRetry={() => void mutateAgents()}
      />
    )
  }

  return (
    <div className="space-y-4" data-review-surface="improve-agent">
      <label className="block space-y-1">
        <span className={TYPE.eyebrow}>Agent</span>
        <select
          value={agentId}
          onChange={(event) => chooseAgent(event.target.value)}
          disabled={applying || agentsLoading}
          aria-label="Agent to improve"
          className={FIELD_CLASS}
        >
          <option value="">{agentsLoading ? "Loading agents…" : agents.length ? "Choose an agent" : "No agents yet"}</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name || agent.role || agent.id}
            </option>
          ))}
        </select>
      </label>

      {!agentsLoading && agents.length === 0 ? (
        <p className={TYPE.meta}>
          Create an agent first.{" "}
          <Link href={APP_ROUTES.agents} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
            Open Agents
          </Link>
        </p>
      ) : null}

      {agentId ? (
        stateError ? (
          <WorkSectionErrorCard
            title="Could not load this agent"
            message="Try again before making changes."
            onRetry={() => void mutateState()}
          />
        ) : stateLoading && !agentState ? (
          <p className="text-sm text-muted-foreground">Loading agent…</p>
        ) : agentState ? (
          <>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
              <dt className={TYPE.meta}>Model</dt>
              <dd className="truncate">{currentModelLabel}</dd>
              <dt className={TYPE.meta}>Fine-tune</dt>
              <dd className="truncate">{currentFineTuneLabel}</dd>
              <dt className={TYPE.meta}>Notes</dt>
              <dd>{agentState.instructions.length}</dd>
              {agentState.supportsKnowledge ? (
                <>
                  <dt className={TYPE.meta}>Knowledge</dt>
                  <dd>{agentState.knowledgeSourceIds.length}</dd>
                </>
              ) : null}
            </dl>

            <ul className="divide-y divide-divide border border-divide" aria-label="Improvements">
              <ImprovementRow
                id="improve-instruction"
                label="Add a coaching note"
                hint="Added to the agent's instructions on every run."
                checked={selection.instruction.enabled}
                disabled={applying}
                onCheckedChange={(checked) => update({ instruction: { ...selection.instruction, enabled: checked } })}
              >
                <Textarea
                  value={selection.instruction.text}
                  onChange={(event) => update({ instruction: { enabled: true, text: event.target.value } })}
                  maxLength={MAX_IMPROVEMENT_NOTE_CHARS}
                  disabled={applying}
                  placeholder="e.g. Always confirm the order number before issuing a refund."
                  aria-label="Coaching note"
                  rows={3}
                />
              </ImprovementRow>

              <ImprovementRow
                id="improve-model"
                label="Switch model"
                hint="The model this agent runs on."
                checked={selection.model.enabled}
                disabled={applying}
                onCheckedChange={(checked) => update({ model: { ...selection.model, enabled: checked } })}
              >
                <select
                  value={selection.model.value}
                  onChange={(event) => update({ model: { enabled: true, value: event.target.value } })}
                  disabled={applying}
                  aria-label="New model"
                  className={FIELD_CLASS}
                >
                  <option value="">Choose a model</option>
                  {modelChoices.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label}
                      {model.id === agentState.model ? " (current)" : ""}
                    </option>
                  ))}
                </select>
              </ImprovementRow>

              {fineTunes.length > 0 ? (
                <ImprovementRow
                  id="improve-fine-tune"
                  label="Attach a fine-tuned model"
                  hint="Used first; falls back to the base model if it fails."
                  checked={selection.fineTune.enabled}
                  disabled={applying}
                  onCheckedChange={(checked) => update({ fineTune: { ...selection.fineTune, enabled: checked } })}
                >
                  <select
                    value={selection.fineTune.id}
                    onChange={(event) => update({ fineTune: { enabled: true, id: event.target.value } })}
                    disabled={applying}
                    aria-label="Fine-tuned model"
                    className={FIELD_CLASS}
                  >
                    <option value="">Choose a fine-tuned model</option>
                    {fineTunes.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name || model.id}
                        {model.id === agentState.trainedModelId ? " (attached)" : ""}
                      </option>
                    ))}
                  </select>
                </ImprovementRow>
              ) : (
                <li className="px-3 py-3">
                  <p className="text-sm font-medium text-muted-foreground">Attach a fine-tuned model</p>
                  <p className={TYPE.meta}>
                    {fineTunesError ? "Fine-tuned models could not be loaded." : "No ready fine-tuned models yet."}{" "}
                    <Link href={APP_ROUTES.training} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
                      Open Training
                    </Link>
                  </p>
                </li>
              )}

              {agentState.supportsKnowledge && sources.length > 0 ? (
                <ImprovementRow
                  id="improve-knowledge"
                  label="Attach knowledge"
                  hint={`Sources the agent should search first. Up to ${MAX_IMPROVEMENT_KNOWLEDGE}.`}
                  checked={selection.knowledge.enabled}
                  disabled={applying}
                  onCheckedChange={(checked) => update({ knowledge: { ...selection.knowledge, enabled: checked } })}
                >
                  <ul className="max-h-48 space-y-1 overflow-y-auto">
                    {sources.map((source) => {
                      const attached = agentState.knowledgeSourceIds.includes(source.id)
                      const picked = selection.knowledge.ids.includes(source.id)
                      return (
                        <li key={source.id} className="flex items-center gap-2">
                          <Checkbox
                            id={`improve-knowledge-${source.id}`}
                            checked={attached || picked}
                            disabled={applying || attached}
                            onCheckedChange={(value) =>
                              update({
                                knowledge: {
                                  enabled: true,
                                  ids:
                                    value === true
                                      ? [...selection.knowledge.ids, source.id]
                                      : selection.knowledge.ids.filter((id) => id !== source.id),
                                },
                              })
                            }
                          />
                          <label htmlFor={`improve-knowledge-${source.id}`} className="min-w-0 truncate text-sm">
                            {source.name || source.id}
                            {attached ? <span className={cn(TYPE.meta, "ml-1")}>attached</span> : null}
                          </label>
                        </li>
                      )
                    })}
                  </ul>
                </ImprovementRow>
              ) : (
                <li className="px-3 py-3">
                  <p className="text-sm font-medium text-muted-foreground">Attach knowledge</p>
                  <p className={TYPE.meta}>
                    {!agentState.supportsKnowledge
                      ? "Add knowledge from the agent's page."
                      : sourcesError
                        ? "Knowledge sources could not be loaded."
                        : "No knowledge sources yet."}
                  </p>
                </li>
              )}
            </ul>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" className="min-h-11" disabled={applying} onClick={() => void apply()}>
                {applying ? "Applying…" : "Apply to agent"}
              </Button>
              {selectedAgent ? (
                <Link
                  href={`${APP_ROUTES.agents}/${encodeURIComponent(selectedAgent.id)}`}
                  className="text-sm font-medium text-[color:var(--g-brand-active)] hover:underline"
                >
                  Open agent
                </Link>
              ) : null}
            </div>
            {formError ? <p role="alert" className="text-sm text-destructive">{formError}</p> : null}
            {applyError ? <p role="alert" className="text-sm text-destructive">{applyError}</p> : null}

            {result ? (
              <section aria-label="Results" className="border border-divide">
                <p className={cn(TYPE.eyebrow, "border-b border-divide px-3 py-2")}>Results</p>
                <ul className="divide-y divide-divide" role="status">
                  {result.data.steps.map((step, index) => {
                    const confirmed = isStepConfirmed(step, result.data.state, result.request)
                    const line = summarizeStep(step, confirmed, names)
                    return (
                      <li key={`${step.kind}-${step.target ?? index}`} className="flex items-start gap-3 px-3 py-2">
                        <span
                          className={cn(
                            "mt-0.5 font-mono text-[10px] uppercase",
                            line.outcome === "confirmed"
                              ? "text-[color:var(--g-brand-active)]"
                              : line.outcome === "failed"
                                ? "text-destructive"
                                : "text-muted-foreground",
                          )}
                        >
                          {line.outcome === "confirmed" ? "Done" : line.outcome === "failed" ? "Failed" : "Check"}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{line.label}</p>
                          <p className={TYPE.meta}>{line.detail}</p>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ) : null}
          </>
        ) : null
      ) : null}
    </div>
  )
}
