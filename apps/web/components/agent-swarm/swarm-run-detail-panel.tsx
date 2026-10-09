"use client"

import { useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import {
  Lightbulb,
  ListChecks,
  Loader2,
  RefreshCw,
  Sparkles,
  StopCircle,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { agentSwarmApi, agentsApi } from "@/lib/api"
import {
  extractCouncilRounds,
  extractDissentingOpinions,
  extractSwarmNextSteps,
  formatSwarmReadableText,
  subtaskReadableSummary,
} from "@/lib/swarm-result-format"
import type { AgentSwarmRun, AgentSwarmSubtask } from "@/types/api"
import {
  SwarmRunStatusBadge,
  SwarmSubtaskStatusBadge,
} from "@/components/agent-swarm/swarm-status-badge"
import {
  isSwarmExecutionUnverified,
  SwarmVerificationLabel,
} from "@/components/agent-swarm/swarm-verification-label"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { SubagentToolGroup } from "@/components/gravitre/agent-ui/subagent-tool-group"
import { cn } from "@/lib/utils"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { useAgentDepartments } from "@/lib/use-agent-departments"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"

const TERMINAL_SUBTASK = new Set(["completed", "failed", "cancelled"])
const ACTIVE_RUN = new Set(["pending", "running", "aggregating"])

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "Not reported"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return "Not reported"
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
  onBusyChange,
  hideClose = false,
}: {
  swarmRunId: string
  onClose: () => void
  onMutateList: () => void
  onBusyChange?: (busy: boolean) => void
  /** Set when a parent drawer already provides its own close control. */
  hideClose?: boolean
}) {
  const { data: agentsData } = useSWR("agent-swarm/detail/agents", () =>
    agentsApi.list(),
  )
  const agentNames = useMemo(
    () =>
      new Map(
        (agentsData?.agents ?? []).map((agent) => [agent.id, agent.name]),
      ),
    [agentsData],
  )
  const [busy, setBusy] = useState<string | null>(null)
  const lock = useRef(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  function begin(kind: string) {
    if (lock.current) return false
    lock.current = true
    setBusy(kind)
    setActionError(null)
    onBusyChange?.(true)
    return true
  }
  function finish() {
    lock.current = false
    setBusy(null)
    onBusyChange?.(false)
  }

  const {
    data: run,
    error,
    isLoading,
    mutate,
  } = useSWR(
    swarmRunId ? `agent-swarm/${swarmRunId}` : null,
    () => agentSwarmApi.get(swarmRunId),
    {
      refreshInterval: (data) =>
        data && ACTIVE_RUN.has(data.status) ? 4000 : 0,
    },
  )

  const executiveSummary = useMemo(
    () => formatSwarmReadableText(run?.finalRecommendation, 100000),
    [run?.finalRecommendation],
  )
  const nextSteps = useMemo(
    () => (run ? extractSwarmNextSteps(run) : []),
    [run],
  )
  const councilRounds = useMemo(
    () => (run ? extractCouncilRounds(run) : []),
    [run],
  )
  const dissent = useMemo(
    () => (run ? extractDissentingOpinions(run) : []),
    [run],
  )

  async function refresh() {
    if (!begin("refresh")) return
    try {
      await mutate()
      onMutateList()
    } catch {
      setActionError(
        "Could not refresh this run. The last reported evidence remains below.",
      )
    } finally {
      finish()
    }
  }
  async function handleAggregate() {
    if (!canAggregate(run) || !begin("aggregate")) return
    try {
      const updated = await agentSwarmApi.aggregate(swarmRunId)
      await mutate(updated, { revalidate: false })
      if (updated.status === "failed") {
        setActionError(
          "The council could not produce a recommendation. Review the reported subtask errors.",
        )
      } else if (updated.status === "completed")
        toast.success("Council result received")
      else toast.message("Aggregation request accepted")
      onMutateList()
    } catch {
      setActionError(
        "Could not aggregate this run. Its existing evidence is retained; try again.",
      )
    } finally {
      finish()
    }
  }
  async function handleCancel() {
    if (!canCancel(run) || !begin("cancel")) return
    try {
      const updated = await agentSwarmApi.cancel(swarmRunId)
      await mutate(updated, { revalidate: false })
      setConfirmCancel(false)
      toast.success("Multi-agent run cancelled")
      onMutateList()
    } catch {
      setActionError(
        "Could not cancel this run. Check its reported status and try again.",
      )
    } finally {
      finish()
    }
  }

  return (
    <Card className="min-w-0 overflow-hidden border-[color:var(--g-border-default)] shadow-none [&_button]:min-h-11">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <CardTitle
              className={cn(
                TYPE.sectionTitle,
                "flex flex-wrap items-center gap-2",
              )}
            >
              Run detail
              {run ? <SwarmRunStatusBadge status={run.status} /> : null}
            </CardTitle>
            <CardDescription className="break-words">
              {run?.objective ?? (isLoading ? "Loading…" : "Select a run")}
            </CardDescription>
          </div>
          {hideClose ? null : (
            <Button
              variant="ghost"
              size="icon"
              className="min-w-11 shrink-0"
              disabled={busy !== null}
              onClick={onClose}
              aria-label="Close detail"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
        {run ? (
          <div className="flex flex-wrap gap-2 pt-2">
            {canAggregate(run) && (
              <Button
                size="sm"
                onClick={() => void handleAggregate()}
                disabled={busy !== null}
              >
                {busy === "aggregate" ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                ) : (
                  <Sparkles className="h-4 w-4 mr-1" />
                )}
                Aggregate
              </Button>
            )}
            {canCancel(run) && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmCancel(true)}
                disabled={busy !== null}
              >
                {busy === "cancel" ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                ) : (
                  <StopCircle className="h-4 w-4 mr-1" />
                )}
                Cancel run
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => void refresh()}
              disabled={busy !== null}
            >
              <RefreshCw
                className={cn(
                  "h-4 w-4 mr-1",
                  busy === "refresh" && "animate-spin",
                )}
              />
              Refresh
            </Button>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4 break-words">
        {actionError ? (
          <p role="alert" className="text-sm text-destructive">
            {actionError}
          </p>
        ) : null}
        {confirmCancel && canCancel(run) ? (
          <section
            aria-label="Confirm cancellation"
            className="space-y-3 border-l-2 border-[color:var(--g-warmth)] pl-3"
          >
            <p className="text-sm">
              Cancel this run? Completed subtask evidence remains available;
              in-flight work will be asked to stop.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={busy !== null}
                onClick={() => setConfirmCancel(false)}
              >
                Keep running
              </Button>
              <Button
                variant="destructive"
                disabled={busy !== null}
                onClick={() => void handleCancel()}
              >
                {busy === "cancel" ? "Cancelling…" : "Confirm cancellation"}
              </Button>
            </div>
          </section>
        ) : null}
        {error ? (
          <WorkSectionErrorCard
            title="Could not refresh run evidence"
            message="Previously reported evidence is retained when available."
            onRetry={() => void refresh()}
          />
        ) : null}
        {isLoading && !run ? (
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
                <dd className="capitalize">
                  {run.decisionMethod
                    ? decisionMethodLabel(run.decisionMethod)
                    : "Not reported"}
                </dd>
              </div>
              {typeof run.finalConfidence === "number" &&
              Number.isFinite(run.finalConfidence) &&
              run.finalConfidence >= 0 &&
              run.finalConfidence <= 1 ? (
                <div>
                  <dt className="text-muted-foreground">Council estimate</dt>
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
              <div
                className={cn(
                  "border px-3 py-2 text-xs",
                  RADIUS.card,
                  STATUS.pending,
                )}
              >
                Council is merging agent outputs into a final recommendation…
              </div>
            ) : null}

            {executiveSummary ? (
              <section
                className={cn(
                  "space-y-2 border-l-2 border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)] p-4",
                  RADIUS.card,
                )}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Sparkles className="h-4 w-4" />
                  Council recommendation
                </div>
                {isSwarmExecutionUnverified(run.executionVerified) ? (
                  <SwarmVerificationLabel />
                ) : null}
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {executiveSummary}
                </p>
                {typeof run.finalConfidence === "number" &&
                Number.isFinite(run.finalConfidence) &&
                run.finalConfidence >= 0 &&
                run.finalConfidence <= 1 ? (
                  <p className="text-xs text-muted-foreground">
                    Reported council estimate; it does not measure execution
                    verification.
                  </p>
                ) : null}
              </section>
            ) : null}

            {run.finalRecommendation &&
            run.finalRecommendation.replace(/\s+/g, " ").trim() !==
              executiveSummary ? (
              <details className="border-t border-border py-2">
                <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
                  Full reported recommendation
                </summary>
                <pre className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
                  {run.finalRecommendation}
                </pre>
              </details>
            ) : null}
            {nextSteps.length > 0 ? (
              <section className="rounded-lg border border-border/70 bg-muted/20 p-4 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <ListChecks className="h-4 w-4 text-[color:var(--g-electric)]" />
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
                    <li
                      key={round.round}
                      className="rounded-lg border border-border/70 p-3 text-sm space-y-2"
                    >
                      <p className="font-medium text-muted-foreground">
                        Round {round.round}
                      </p>
                      {round.reasoning ? (
                        <p className="text-foreground/90">{round.reasoning}</p>
                      ) : null}
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
                <p className="text-xs font-medium text-muted-foreground">
                  Alternate views
                </p>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {dissent.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {run.subtasks === undefined ? (
              <p className={TYPE.bodyMuted}>Subtask evidence not reported.</p>
            ) : run.subtasks.length === 0 ? (
              <p className={TYPE.bodyMuted}>
                No subtasks returned for this run.
              </p>
            ) : (
              <SubagentToolGroup count={run.subtasks.length}>
                <ul className="space-y-2">
                  {(run.subtasks ?? []).map((subtask) => (
                    <SubtaskCard
                      key={subtask.id}
                      subtask={subtask}
                      agentName={agentNames.get(subtask.agentId)}
                    />
                  ))}
                </ul>
              </SubagentToolGroup>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

function SubtaskCard({
  subtask,
  agentName,
}: {
  subtask: AgentSwarmSubtask
  agentName?: string
}) {
  const summary = subtaskReadableSummary(subtask)
  const departmentOf = useAgentDepartments()

  return (
    <li className="list-none space-y-1.5 border-t border-border py-3 text-sm">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="flex items-center gap-1.5 font-medium">
          <DepartmentIcon department={departmentOf({ id: subtask.agentId, name: agentName })} size="xs" />
          {agentName ?? `Agent ${subtask.agentId.slice(0, 8)}`}
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
      {subtask.result ? (
        <details className="border-t border-border pt-2">
          <summary className="min-h-11 cursor-pointer py-3 text-sm">
            Full reported result
          </summary>
          <pre className="whitespace-pre-wrap break-words text-xs text-muted-foreground">
            {JSON.stringify(subtask.result, null, 2)}
          </pre>
        </details>
      ) : null}
      {subtask.errorMessage ? (
        <p className="text-destructive text-xs">{subtask.errorMessage}</p>
      ) : null}
    </li>
  )
}
