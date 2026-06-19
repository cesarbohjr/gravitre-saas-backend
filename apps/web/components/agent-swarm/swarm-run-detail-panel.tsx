"use client"

import { useState } from "react"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import {
  Bot,
  Loader2,
  RefreshCw,
  Sparkles,
  StopCircle,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { agentSwarmApi } from "@/lib/api"
import type { AgentSwarmRun, AgentSwarmSubtask } from "@/types/api"
import { SwarmRunStatusBadge, SwarmSubtaskStatusBadge } from "@/components/agent-swarm/swarm-status-badge"
import { cn } from "@/lib/utils"

const TERMINAL_SUBTASK = new Set(["completed", "failed", "cancelled"])
const ACTIVE_RUN = new Set(["pending", "running", "aggregating"])

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "—"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

function canAggregate(run: AgentSwarmRun | undefined) {
  if (!run || run.status !== "running") return false
  const subtasks = run.subtasks ?? []
  if (subtasks.length === 0) return false
  return subtasks.every((s) => TERMINAL_SUBTASK.has(s.status))
}

function canCancel(run: AgentSwarmRun | undefined) {
  return run ? ACTIVE_RUN.has(run.status) : false
}

function subtaskSummary(subtask: AgentSwarmSubtask) {
  const result = subtask.result
  if (!result || typeof result !== "object") return null
  const summary = result.summary ?? result.finding ?? result.recommendedAction ?? result.recommended_action
  return typeof summary === "string" && summary.trim() ? summary.trim() : null
}

export function SwarmRunDetailPanel({
  swarmRunId,
  onClose,
  onMutateList,
}: {
  swarmRunId: string
  onClose: () => void
  onMutateList: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)

  const { data: run, error, isLoading, mutate } = useSWR(
    swarmRunId ? `agent-swarm/${swarmRunId}` : null,
    () => agentSwarmApi.get(swarmRunId),
    {
      refreshInterval: (data) => (data && ACTIVE_RUN.has(data.status) ? 4000 : 0),
    },
  )

  async function refresh() {
    setBusy("refresh")
    try {
      await mutate()
      onMutateList()
    } finally {
      setBusy(null)
    }
  }

  async function handleAggregate() {
    if (!run) return
    setBusy("aggregate")
    try {
      await agentSwarmApi.aggregate(swarmRunId)
      toast.success("Swarm aggregated")
      await mutate()
      onMutateList()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Aggregation failed")
    } finally {
      setBusy(null)
    }
  }

  async function handleCancel() {
    if (!run) return
    setBusy("cancel")
    try {
      await agentSwarmApi.cancel(swarmRunId)
      toast.success("Swarm cancelled")
      await mutate()
      onMutateList()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Cancel failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="border-border/80 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <CardTitle className="text-base flex items-center gap-2 flex-wrap">
              Swarm detail
              {run ? <SwarmRunStatusBadge status={run.status} /> : null}
            </CardTitle>
            <CardDescription className="line-clamp-3">
              {run?.objective ?? (isLoading ? "Loading…" : "Select a run")}
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" className="shrink-0" onClick={onClose} aria-label="Close detail">
            <X className="h-4 w-4" />
          </Button>
        </div>
        {run ? (
          <div className="flex flex-wrap gap-2 pt-2">
            {canAggregate(run) && (
              <Button size="sm" onClick={() => void handleAggregate()} disabled={busy !== null}>
                {busy === "aggregate" ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Sparkles className="h-4 w-4 mr-1" />}
                Aggregate
              </Button>
            )}
            {canCancel(run) && (
              <Button size="sm" variant="outline" onClick={() => void handleCancel()} disabled={busy !== null}>
                {busy === "cancel" ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <StopCircle className="h-4 w-4 mr-1" />}
                Cancel
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => void refresh()} disabled={busy !== null}>
              <RefreshCw className={cn("h-4 w-4 mr-1", busy === "refresh" && "animate-spin")} />
              Refresh
            </Button>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <p className="text-sm text-destructive">Failed to load swarm run.</p>
        ) : isLoading && !run ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading run…
          </div>
        ) : run ? (
          <>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div>
                <dt className="text-muted-foreground">Started</dt>
                <dd>{formatRelative(run.createdAt)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Decision</dt>
                <dd className="capitalize">{run.decisionMethod.replace(/_/g, " ")}</dd>
              </div>
              {run.finalRecommendation ? (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Recommendation</dt>
                  <dd className="mt-1 rounded-md bg-muted/50 p-2 text-foreground">{run.finalRecommendation}</dd>
                </div>
              ) : null}
              {run.finalConfidence != null ? (
                <div>
                  <dt className="text-muted-foreground">Confidence</dt>
                  <dd>{Math.round(run.finalConfidence * 100)}%</dd>
                </div>
              ) : null}
              {run.errorMessage ? (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Error</dt>
                  <dd className="text-destructive">{run.errorMessage}</dd>
                </div>
              ) : null}
            </dl>

            <div className="space-y-2">
              <h4 className="text-sm font-medium">Subtasks</h4>
              <ul className="space-y-2">
                {(run.subtasks ?? []).map((subtask) => (
                  <li
                    key={subtask.id}
                    className="rounded-lg border border-border/70 p-3 text-sm space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="flex items-center gap-1.5 font-medium">
                        <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                        Agent {subtask.agentId.slice(0, 8)}
                      </span>
                      <SwarmSubtaskStatusBadge status={subtask.status} />
                    </div>
                    <p className="text-muted-foreground">{subtask.taskPrompt}</p>
                    {subtaskSummary(subtask) ? (
                      <p className="text-foreground/90 border-t border-border/50 pt-2">{subtaskSummary(subtask)}</p>
                    ) : null}
                    {subtask.errorMessage ? (
                      <p className="text-destructive text-xs">{subtask.errorMessage}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
