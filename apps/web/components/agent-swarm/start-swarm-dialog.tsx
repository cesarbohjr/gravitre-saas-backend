"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Loader2, Network, Plus, Trash2 } from "lucide-react"
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
import { agentSwarmApi, agentsApi } from "@/lib/api"
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

  const { data: agentsData, isLoading: loadingAgents } = useSWR(
    open ? "agent-swarm/start/agents" : null,
    () => agentsApi.list(),
  )

  const agents = useMemo(() => agentsData?.agents ?? [], [agentsData])

  function reset() {
    setParentAgentId("")
    setObjective("")
    setDecisionMethod("majority_vote")
    setSubtasks([{ ...EMPTY_SUBTASK }])
    setSubmitting(false)
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
  }

  function removeSubtask(index: number) {
    setSubtasks((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)))
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const run = await agentSwarmApi.start({
        parentAgentId,
        objective: objective.trim(),
        decisionMethod,
        subtasks: validSubtasks.map((s) => ({
          agentId: s.agentId,
          task: s.task.trim(),
        })),
      })
      toast.success("Swarm run started")
      onStarted(run.id)
      handleOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start swarm")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Network className="h-5 w-5 text-violet-500" />
            Start agent swarm
          </DialogTitle>
          <DialogDescription>
            Coordinate multiple agents on subtasks, then aggregate results through the council pattern.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="swarm-parent">Parent agent</Label>
            <Select value={parentAgentId} onValueChange={setParentAgentId} disabled={loadingAgents}>
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

          <div className="space-y-2">
            <Label htmlFor="swarm-objective">Objective</Label>
            <Textarea
              id="swarm-objective"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="What should this swarm accomplish?"
              rows={3}
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
                <Select
                  value={subtask.agentId}
                  onValueChange={(v) => updateSubtask(index, { agentId: v })}
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
                <Input
                  value={subtask.task}
                  onChange={(e) => updateSubtask(index, { task: e.target.value })}
                  placeholder="Task prompt for this agent"
                />
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={() => void handleSubmit()} disabled={!canSubmit || submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Start swarm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
