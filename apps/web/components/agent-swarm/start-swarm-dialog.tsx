"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Loader2, Plus, Trash2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { agentSwarmApi, agentsApi, marketplaceApi } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import {
  collectInstalledAgentIds,
  resolveSwarmAgentDefaults,
} from "@/lib/resolve-default-agent"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { AgentSwarmDecisionMethod } from "@/types/api"

const METHODS: {
  value: AgentSwarmDecisionMethod
  label: string
  hint: string
}[] = [
  {
    value: "majority_vote",
    label: "Majority vote",
    hint: "Use the position supported by most council participants.",
  },
  {
    value: "unanimous",
    label: "Unanimous",
    hint: "Seek agreement across all council participants.",
  },
  {
    value: "weighted_vote",
    label: "Weighted vote",
    hint: "Weight reported council opinions by their confidence estimates.",
  },
  {
    value: "chair_decides",
    label: "Chair decides",
    hint: "Use the chair's position when the council reports one.",
  },
]
type Draft = { id: number; agentId: string; task: string }

/** Prefill from a starter question: objective plus one subtask per chosen agent. */
export interface SwarmStartPreset {
  objective: string
  subtasks: Array<{ agentId: string; task: string }>
}
const selectClass =
  "min-h-11 w-full rounded-md border border-input bg-background px-3 text-sm"

export function StartSwarmDialog({
  open,
  onOpenChange,
  onStarted,
  preset,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: (id: string) => void
  preset?: SwarmStartPreset | null
}) {
  const [parentAgentId, setParentAgentId] = useState("")
  const [objective, setObjective] = useState("")
  const [decisionMethod, setDecisionMethod] =
    useState<AgentSwarmDecisionMethod>("majority_vote")
  const [subtasks, setSubtasks] = useState<Draft[]>([
    { id: 0, agentId: "", task: "" },
  ])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lock = useRef(false)
  const resolved = useRef(false)
  const nextId = useRef(1)
  const {
    data: agentsData,
    error: agentsError,
    isLoading: loadingAgents,
    mutate: retryAgents,
  } = useSWR(open ? "agent-swarm/start/agents" : null, () => agentsApi.list())
  const {
    data: installsData,
    error: installsError,
    isLoading: loadingInstalls,
    mutate: retryInstalls,
  } = useSWR(open ? "agent-swarm/start/installs" : null, () =>
    marketplaceApi.listInstalls({ status: "active", limit: 100 }),
  )
  const agents = useMemo(() => agentsData?.agents ?? [], [agentsData])
  const installedIds = useMemo(
    () => collectInstalledAgentIds(installsData?.installs ?? []),
    [installsData],
  )

  useEffect(() => {
    if (!open || !preset) return
    setObjective(preset.objective)
    if (preset.subtasks.length > 0) {
      resolved.current = true
      setParentAgentId(preset.subtasks[0].agentId)
      setSubtasks(
        preset.subtasks.map((s) => ({
          id: nextId.current++,
          agentId: s.agentId,
          task: s.task,
        })),
      )
    }
  }, [open, preset])

  useEffect(() => {
    if (
      !open ||
      resolved.current ||
      loadingAgents ||
      loadingInstalls ||
      !agents.length
    )
      return
    const defaults = resolveSwarmAgentDefaults({
      agents,
      installedAgentIds: installedIds,
    })
    if (!defaults) return
    resolved.current = true
    setParentAgentId(defaults.parentAgentId)
    setSubtasks(
      defaults.subtaskAgentIds.map((agentId) => ({
        id: nextId.current++,
        agentId,
        task: "",
      })),
    )
  }, [open, loadingAgents, loadingInstalls, agents, installedIds])

  function close(next: boolean) {
    if (lock.current) return
    if (!next) {
      setObjective("")
      setParentAgentId("")
      setDecisionMethod("majority_vote")
      setSubtasks([{ id: nextId.current++, agentId: "", task: "" }])
      setError(null)
      resolved.current = false
    }
    onOpenChange(next)
  }
  function update(id: number, patch: Partial<Draft>) {
    resolved.current = true
    setSubtasks((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    )
  }
  const canSubmit =
    !loadingAgents &&
    Boolean(agentsData) &&
    agents.some((a) => a.id === parentAgentId) &&
    Boolean(objective.trim()) &&
    subtasks.length > 0 &&
    subtasks.length <= 10 &&
    subtasks.every(
      (s) => agents.some((a) => a.id === s.agentId) && s.task.trim(),
    )
  async function submit() {
    if (!canSubmit || lock.current) return
    lock.current = true
    setSubmitting(true)
    setError(null)
    try {
      const org = await ensureSelectedOrg(true)
      if (!org)
        throw new Error("Workspace membership is required to start a run.")
      const run = await agentSwarmApi.start({
        parentAgentId,
        objective: objective.trim(),
        decisionMethod,
        subtasks: subtasks.map(({ agentId, task }) => ({
          agentId,
          task: task.trim(),
        })),
      })
      toast.success("Multi-agent run started")
      lock.current = false
      close(false)
      onStarted(run.id)
    } catch {
      setError(
        "Could not start this run. Your objective and subtasks are retained; try again.",
      )
    } finally {
      lock.current = false
      setSubmitting(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        className="max-h-[90dvh] max-w-2xl overflow-y-auto"
        data-composition="create"
      >
        <DialogHeader>
          <p className={TYPE.eyebrow}>Coordinate / New run</p>
          <DialogTitle className="font-sans">
            Give each agent a clear part
          </DialogTitle>
          <DialogDescription>
            Set one objective, divide the work, then review the council’s
            reported recommendation. Starting a run dispatches the subtasks.
          </DialogDescription>
        </DialogHeader>
        {loadingAgents ? (
          <p role="status" className={TYPE.bodyMuted}>
            Loading agents…
          </p>
        ) : null}
        {agentsError ? (
          <div role="alert" className="space-y-2 text-sm">
            <p>Could not load agents.</p>
            <Button
              variant="outline"
              className="min-h-11"
              onClick={() => void retryAgents()}
            >
              Retry agents
            </Button>
          </div>
        ) : null}
        {agentsData && !agents.length && !agentsError ? (
          <p className={TYPE.bodyMuted}>
            Add an agent to your AI Team before starting a run.
          </p>
        ) : null}
        {installsError ? (
          <div className="text-sm text-muted-foreground">
            <p>
              Pack preferences are unavailable. You can choose workspace agents
              below.
            </p>
            <Button
              variant="ghost"
              className="min-h-11"
              onClick={() => void retryInstalls()}
            >
              Retry pack preferences
            </Button>
          </div>
        ) : null}
        <fieldset
          disabled={submitting || loadingAgents || !agents.length}
          className="min-w-0 space-y-5"
        >
          <div className="space-y-2">
            <Label htmlFor="swarm-objective">Objective</Label>
            <Textarea
              id="swarm-objective"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              rows={3}
              placeholder="What outcome should these agents work toward?"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="swarm-parent">Coordinator</Label>
              <select
                id="swarm-parent"
                className={selectClass}
                value={parentAgentId}
                onChange={(e) => {
                  resolved.current = true
                  setParentAgentId(e.target.value)
                }}
              >
                <option value="">Choose coordinator</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="swarm-decision">Decision method</Label>
              <select
                id="swarm-decision"
                className={selectClass}
                value={decisionMethod}
                onChange={(e) =>
                  setDecisionMethod(e.target.value as AgentSwarmDecisionMethod)
                }
              >
                {METHODS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className={TYPE.meta}>
            Roster suggestions use available workspace agents and pack
            preferences. You can change every role.{" "}
            {METHODS.find((m) => m.value === decisionMethod)?.hint} Council
            confidence is an estimate, not proof of execution.
          </p>
          <section className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className={TYPE.sectionTitle}>
                Work split{" "}
                <span className={TYPE.meta}>{subtasks.length}/10</span>
              </h3>
              <Button
                variant="ghost"
                className="min-h-11"
                disabled={subtasks.length >= 10}
                onClick={() => {
                  resolved.current = true
                  setSubtasks((rows) => [
                    ...rows,
                    { id: nextId.current++, agentId: "", task: "" },
                  ])
                }}
              >
                <Plus className="mr-1 h-4 w-4" />
                Add subtask
              </Button>
            </div>
            {subtasks.map((s, index) => (
              <div
                key={s.id}
                className="grid gap-3 border-t border-border py-3 sm:grid-cols-[2.5rem_minmax(0,1fr)]"
              >
                <span
                  className={cn(
                    TYPE.eyebrow,
                    "pt-3 text-[color:var(--g-electric)]",
                  )}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="sr-only" htmlFor={`swarm-worker-${s.id}`}>
                      Agent for subtask {index + 1}
                    </label>
                    <select
                      id={`swarm-worker-${s.id}`}
                      className={selectClass}
                      value={s.agentId}
                      onChange={(e) =>
                        update(s.id, { agentId: e.target.value })
                      }
                    >
                      <option value="">Choose agent</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      className="min-h-11 min-w-11 shrink-0"
                      aria-label={`Remove subtask ${index + 1}`}
                      disabled={subtasks.length === 1}
                      onClick={() =>
                        setSubtasks((rows) =>
                          rows.filter((row) => row.id !== s.id),
                        )
                      }
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <Input
                    className="min-h-11"
                    aria-label={`Task for subtask ${index + 1}`}
                    value={s.task}
                    onChange={(e) => update(s.id, { task: e.target.value })}
                    placeholder="Describe this agent’s part"
                  />
                </div>
              </div>
            ))}
            <p className={TYPE.meta}>
              Complete every subtask or remove it before starting.
            </p>
          </section>
        </fieldset>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            variant="outline"
            className="min-h-11"
            disabled={submitting}
            onClick={() => close(false)}
          >
            Cancel
          </Button>
          <Button
            className="min-h-11"
            disabled={!canSubmit || submitting}
            onClick={() => void submit()}
          >
            {submitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin motion-reduce:animate-none" />
            ) : null}
            {submitting ? "Starting…" : "Start multi-agent run"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
