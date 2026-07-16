"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { ChevronDown, ChevronRight, Loader2, Network, Plus, Trash2 } from "lucide-react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { agentSwarmApi, agentsApi, marketplaceApi } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import {
  collectInstalledAgentIds,
  resolveSwarmAgentDefaults,
} from "@/lib/resolve-default-agent"
import type { AgentSwarmDecisionMethod } from "@/types/api"

type SubtaskDraft = { agentId: string; task: string }

const DECISION_METHODS: { value: AgentSwarmDecisionMethod; label: string }[] = [
  { value: "majority_vote", label: "Majority vote" },
  { value: "unanimous", label: "Unanimous" },
  { value: "weighted_vote", label: "Weighted vote" },
  { value: "chair_decides", label: "Chair decides" },
]

const EMPTY_SUBTASK: SubtaskDraft = { agentId: "", task: "" }

export function StartSwarmDialog({
  open,
  onOpenChange,
  onStarted,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: (swarmRunId: string) => void
}) {
  const [parentAgentId, setParentAgentId] = useState("")
  const [objective, setObjective] = useState("")
  const [decisionMethod, setDecisionMethod] = useState<AgentSwarmDecisionMethod>("majority_vote")
  const [subtasks, setSubtasks] = useState<SubtaskDraft[]>([{ ...EMPTY_SUBTASK }])
  const [submitting, setSubmitting] = useState(false)
  const [showAdvancedAgents, setShowAdvancedAgents] = useState(false)
  const [agentsAutoResolved, setAgentsAutoResolved] = useState(false)
  const autoResolvedRef = useRef(false)

  const { data: agentsData, isLoading: loadingAgents } = useSWR(
    open ? "agent-swarm/start/agents" : null,
    () => agentsApi.list(),
  )
  const { data: installsData } = useSWR(
    open ? "agent-swarm/start/installs" : null,
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
  )

  const agents = useMemo(() => agentsData?.agents ?? [], [agentsData])
  const installedAgentIds = useMemo(
    () => collectInstalledAgentIds(installsData?.installs ?? []),
    [installsData?.installs],
  )

  useEffect(() => {
    if (!open || autoResolvedRef.current || loadingAgents || agents.length === 0) return
    const defaults = resolveSwarmAgentDefaults({ agents, installedAgentIds })
    if (!defaults) return
    autoResolvedRef.current = true
    setParentAgentId(defaults.parentAgentId)
    setSubtasks(
      defaults.subtaskAgentIds.map((agentId) => ({
        agentId,
        task: "",
      })),
    )
    setAgentsAutoResolved(true)
    setShowAdvancedAgents(false)
  }, [open, loadingAgents, agents, installedAgentIds])

  function reset() {
    setParentAgentId("")
    setObjective("")
    setDecisionMethod("majority_vote")
    setSubtasks([{ ...EMPTY_SUBTASK }])
    setSubmitting(false)
    setShowAdvancedAgents(false)
    setAgentsAutoResolved(false)
    autoResolvedRef.current = false
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    onOpenChange(next)
  }

  const validSubtasks = subtasks.filter((s) => s.agentId && s.task.trim())
  const canSubmit =
    Boolean(parentAgentId) &&
    objective.trim().length > 0 &&
    validSubtasks.length >= 1 &&
    validSubtasks.length <= 10

  function updateSubtask(index: number, patch: Partial<SubtaskDraft>) {
    setSubtasks((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  function addSubtask() {
    if (subtasks.length >= 10) return
    setSubtasks((prev) => [...prev, { ...EMPTY_SUBTASK }])
    setShowAdvancedAgents(true)
  }

  function removeSubtask(index: number) {
    setSubtasks((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      await ensureSelectedOrg(true)
      const run = await agentSwarmApi.start({
        parentAgentId,
        objective: objective.trim(),
        decisionMethod,
        subtasks: validSubtasks.map((s) => ({
          agentId: s.agentId,
          task: s.task.trim(),
        })),
      })
      toast.success("Multi-agent run started")
      onStarted(run.id)
      handleOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start multi-agent run")
    } finally {
      setSubmitting(false)
    }
  }

  const parentAgent = agents.find((agent) => agent.id === parentAgentId)
  const workerNames = subtasks
    .map((s) => agents.find((agent) => agent.id === s.agentId)?.name)
    .filter(Boolean)

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Network className="h-5 w-5 text-violet-500" />
            Start multi-agent run
          </DialogTitle>
          <DialogDescription>
            Coordinate multiple agents on subtasks, then merge their results into one recommendation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {agentsAutoResolved && parentAgent ? (
            <div className="rounded-lg border border-border bg-secondary/40 px-3 py-2.5 text-sm">
              <p className="font-medium text-foreground">
                Auto-selected from your packs · {parentAgent.name}
                {workerNames.length > 0 ? ` + ${workerNames.length} worker${workerNames.length === 1 ? "" : "s"}` : ""}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Add subtask prompts below. Change agents only if you need a different roster.
              </p>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="swarm-objective">Objective</Label>
            <Textarea
              id="swarm-objective"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="What should this multi-agent run accomplish?"
              rows={3}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="swarm-decision">Decision method</Label>
            <Select
              value={decisionMethod}
              onValueChange={(v) => setDecisionMethod(v as AgentSwarmDecisionMethod)}
            >
              <SelectTrigger id="swarm-decision">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DECISION_METHODS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Subtasks ({validSubtasks.length}/10)</Label>
              <Button type="button" variant="ghost" size="sm" onClick={addSubtask} disabled={subtasks.length >= 10}>
                <Plus className="h-4 w-4 mr-1" />
                Add
              </Button>
            </div>
            {subtasks.map((subtask, index) => (
              <div key={index} className="rounded-lg border border-border p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-muted-foreground">Subtask {index + 1}</span>
                  {subtasks.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => removeSubtask(index)}
                      aria-label="Remove subtask"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                {showAdvancedAgents || !agentsAutoResolved ? (
                  <Select
                    value={subtask.agentId}
                    onValueChange={(v) => {
                      updateSubtask(index, { agentId: v })
                      setAgentsAutoResolved(false)
                    }}
                    disabled={loadingAgents}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Assign agent" />
                    </SelectTrigger>
                    <SelectContent>
                      {agents.map((agent) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Agent: {agents.find((a) => a.id === subtask.agentId)?.name || "Auto-selected"}
                  </p>
                )}
                <Input
                  value={subtask.task}
                  onChange={(e) => updateSubtask(index, { task: e.target.value })}
                  placeholder="Task prompt for this agent"
                />
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-border">
            <button
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-muted-foreground hover:bg-secondary/40"
              onClick={() => setShowAdvancedAgents((v) => !v)}
            >
              {showAdvancedAgents ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              Advanced: choose agents
            </button>
            {showAdvancedAgents ? (
              <div className="space-y-3 border-t border-border px-3 py-3">
                <div className="space-y-2">
                  <Label htmlFor="swarm-parent">Parent agent</Label>
                  <Select
                    value={parentAgentId}
                    onValueChange={(v) => {
                      setParentAgentId(v)
                      setAgentsAutoResolved(false)
                    }}
                    disabled={loadingAgents}
                  >
                    <SelectTrigger id="swarm-parent">
                      <SelectValue placeholder={loadingAgents ? "Loading agents…" : "Select coordinator agent"} />
                    </SelectTrigger>
                    <SelectContent>
                      {agents.map((agent) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <p className="text-xs text-muted-foreground">
                  Subtask agent dropdowns are shown above when advanced is open.
                </p>
              </div>
            ) : null}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={() => void handleSubmit()} disabled={!canSubmit || submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Start multi-agent run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
