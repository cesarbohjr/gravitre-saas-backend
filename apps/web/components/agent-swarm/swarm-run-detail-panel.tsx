"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import {
  Bot,
  CheckCircle2,
  Lightbulb,
  ListChecks,
  Loader2,
  RefreshCw,
  Sparkles,
  StopCircle,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { agentSwarmApi } from "@/lib/api"
import {
  extractCouncilRounds,
  extractDissentingOpinions,
  extractSwarmNextSteps,
  formatSwarmReadableText,
  subtaskReadableSummary,
} from "@/lib/swarm-result-format"
import type { AgentSwarmRun, AgentSwarmSubtask } from "@/types/api"
import { SwarmRunStatusBadge, SwarmSubtaskStatusBadge } from "@/components/agent-swarm/swarm-status-badge"
import {
  isSwarmExecutionUnverified,
  SwarmVerificationLabel,
} from "@/components/agent-swarm/swarm-verification-label"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { SubagentToolGroup } from "@/components/gravitre/agent-ui/subagent-tool-group"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS } from "@/lib/design-system"

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

function decisionMethodLabel(method: string) {
  return method.replace(/_/g, " ")
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

  const executiveSummary = useMemo(
    () => formatSwarmReadableText(run?.finalRecommendation, 900),
    [run?.finalRecommendation],
  )
  const nextSteps = useMemo(() => (run ? extractSwarmNextSteps(run) : []), [run])
  const councilRounds = useMemo(() => (run ? extractCouncilRounds(run) : []), [run])
  const dissent = useMemo(() => (run ? extractDissentingOpinions(run) : []), [run])

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
      toast.success("Multi-agent run aggregated")
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
      toast.success("Multi-agent run cancelled")
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
              Run detail
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
          <p className="text-sm text-destructive">Failed to load multi-agent run.</p>
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
                <dd className="capitalize">{decisionMethodLabel(run.decisionMethod)}</dd>
              </div>
              {run.finalConfidence != null ? (
                <div>
                  <dt className="text-muted-foreground">Council confidence</dt>
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

            {run.status === "aggregating" ? (
              <div className={cn("border px-3 py-2 text-xs", RADIUS.card, STATUS.pending)}>
                Council is merging agent outputs into a final recommendation…
              </div>
            ) : null}

            {executiveSummary ? (
              <section className={cn("space-y-2 border p-4", RADIUS.card, STATUS.verified)}>
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  Council recommendation
                </div>
                {isSwarmExecutionUnverified(run.executionVerified) ? <SwarmVerificationLabel /> : null}
                <p className="text-sm leading-relaxed text-foreground">{executiveSummary}</p>
                {run.finalConfidence != null ? (
                  <p className="text-xs text-muted-foreground">
                    Based on {decisionMethodLabel(run.decisionMethod)} across {(run.subtasks ?? []).length} agent
                    {(run.subtasks ?? []).length === 1 ? "" : "s"}.
                  </p>
                ) : null}
              </section>
            ) : null}

            {nextSteps.length > 0 ? (
              <section className="rounded-lg border border-border/70 bg-muted/20 p-4 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <ListChecks className="h-4 w-4 text-violet-500" />
                  Suggested next steps
                </div>
                <ol className="list-decimal list-inside space-y-1.5 text-sm text-foreground/90">
                  {nextSteps.map((step) => (
                    <li key={step} className="leading-relaxed">
                      {step}
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}

            {councilRounds.length > 0 ? (
              <section className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Lightbulb className="h-4 w-4 text-[color:var(--status-pending)]" />
                  How the council decided
                </div>
                <ul className="space-y-2">
                  {councilRounds.map((round) => (
                    <li key={round.round} className="rounded-lg border border-border/70 p-3 text-sm space-y-2">
                      <p className="font-medium text-muted-foreground">Round {round.round}</p>
                      {round.reasoning ? <p className="text-foreground/90">{round.reasoning}</p> : null}
                      {round.keyPoints.length > 0 ? (
                        <ul className="list-disc list-inside text-foreground/90 space-y-0.5">
                          {round.keyPoints.map((point) => (
                            <li key={point}>{point}</li>
                          ))}
                        </ul>
                      ) : null}
                      {round.concerns.length > 0 ? (
                        <div className="text-xs text-[color:var(--status-pending)]">
                          Open concerns: {round.concerns.join(" · ")}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {dissent.length > 0 ? (
              <section className="rounded-lg border border-dashed border-border/80 p-3 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Alternate views</p>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {dissent.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            <SubagentToolGroup count={(run.subtasks ?? []).length}>
              <ul className="space-y-2">
                {(run.subtasks ?? []).map((subtask) => (
                  <SubtaskCard key={subtask.id} subtask={subtask} />
                ))}
              </ul>
            </SubagentToolGroup>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

function SubtaskCard({ subtask }: { subtask: AgentSwarmSubtask }) {
  const summary = subtaskReadableSummary(subtask)

  return (
    <li className="rounded-lg border border-border/70 p-3 text-sm space-y-1.5 list-none">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="flex items-center gap-1.5 font-medium">
          <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          Agent {subtask.agentId.slice(0, 8)}
        </span>
        <SwarmSubtaskStatusBadge status={subtask.status} />
      </div>
      <p className="text-muted-foreground">{subtask.taskPrompt}</p>
      {summary ? (
        <div className="text-foreground/90 border-t border-border/50 pt-2 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <ExecutionModeBadge source={subtask.result} compact />
            {isSwarmExecutionUnverified(subtask.executionVerified) ? (
              <SwarmVerificationLabel compact />
            ) : null}
          </div>
          <p className="leading-relaxed">{summary}</p>
        </div>
      ) : null}
      {subtask.errorMessage ? (
        <p className="text-destructive text-xs">{subtask.errorMessage}</p>
      ) : null}
    </li>
  )
}
