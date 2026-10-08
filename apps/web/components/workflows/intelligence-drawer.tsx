"use client"

import { useState, useCallback } from "react"
import { useReducedMotion } from "framer-motion"
import {
  formatSimulationDuration as formatMs,
  simulationDuration,
  totalSimulationDuration,
  reportedCount,
  isSuccessfulWorkflowStatus,
} from "@/lib/workflow-evidence"
import { motion } from "framer-motion"
import {
  GitBranch,
  Beaker,
  ShieldAlert,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
  Database,
  Zap,
  ChevronRight,
  Info,
  ServerCrash,
} from "lucide-react"
import { Sheet, SheetContent, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { Illustration, type IllustrationName } from "@/components/gravitre/illustration"
import { workflowsApi } from "@/lib/api"
import type {
  WorkflowDigitalTwinResponse,
  WorkflowDryRunResponse,
  WorkflowFailureAlert,
} from "@/types/api"

type DrawerTab = "simulate" | "risk" | "dryrun"

export interface IntelligenceDrawerNode {
  id: string
  name: string
  type: string
}

interface IntelligenceDrawerProps {
  open: boolean
  onClose: () => void
  workflowId: string
  /** Whether the workflow id is a persisted UUID (vs a local/demo draft). */
  isPersisted: boolean
  nodes: IntelligenceDrawerNode[]
  initialTab?: DrawerTab
  /** Prefetched dry-run result (e.g. from Preview) — avoids auto-run effects. */
  prefetchedDryRun?: WorkflowDryRunResponse | null
}

interface SimulatedStep {
  id: string
  name: string
  type: string
  predictedMs: number | null
  source: "fixture" | "llm" | "unknown"
  note: string
}

interface DryRunStep {
  id: string
  name: string
  type: string
  status: string
  error?: string | null
}

const TABS: { id: DrawerTab; label: string; icon: typeof Beaker }[] = [
  { id: "simulate", label: "Timing evidence", icon: Clock },
  { id: "risk", label: "Risk scan", icon: ShieldAlert },
  { id: "dryrun", label: "Dry run", icon: Play },
]

const SEVERITY_STYLES: Record<
  string,
  { dot: string; text: string; border: string; bg: string; label: string }
> = {
  critical: {
    dot: "bg-destructive",
    text: "text-destructive",
    border: "border-destructive/40",
    bg: "bg-destructive/10",
    label: "Critical",
  },
  high: {
    dot: "bg-[color:var(--status-rejected)]",
    text: "text-[color:var(--status-rejected)]",
    border: "border-[color:var(--status-rejected)]/40",
    bg: "bg-[color:var(--status-rejected)]/10",
    label: "High",
  },
  medium: {
    dot: "bg-[color:var(--status-pending)]",
    text: "text-[color:var(--status-pending)]",
    border: "border-[color:var(--status-pending)]/40",
    bg: "bg-[color:var(--status-pending)]/10",
    label: "Medium",
  },
  low: {
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
    border: "border-border",
    bg: "bg-muted/40",
    label: "Low",
  },
}

function mapDigitalTwinSteps(
  rawSteps: Array<Record<string, unknown>>,
  canvasNodes: IntelligenceDrawerNode[],
): SimulatedStep[] {
  const nodeById = new Map(canvasNodes.map((node) => [node.id, node]))
  return rawSteps.map((step, index) => {
    const stepId = String(step.step_id ?? step.stepId ?? `step-${index}`)
    const canvasNode = nodeById.get(stepId)
    const nodeType = canvasNode?.type ?? String(step.step_type ?? step.stepType ?? "task")
    const output = (step.output_snapshot ?? step.outputSnapshot ?? {}) as Record<string, unknown>
    const rawSource = String(output.source ?? "")
    const source =
      rawSource === "fixture" || rawSource === "live_read"
        ? ("fixture" as const)
        : rawSource === "llm"
          ? ("llm" as const)
          : ("unknown" as const)
    const predictedMs = simulationDuration(step)
    const note =
      rawSource === "fixture"
        ? "Connector fixture replay"
        : rawSource === "live_read"
          ? "Knowledge read in simulation"
          : rawSource === "llm"
            ? "AI simulation"
            : "Source not reported"
    return {
      id: stepId,
      name: canvasNode?.name ?? String(step.step_name ?? step.stepName ?? `Step ${index + 1}`),
      type: nodeType,
      predictedMs,
      source,
      note,
    }
  })
}

function mapDryRunSteps(raw: Array<Record<string, unknown>>): DryRunStep[] {
  return raw.map((s, i) => ({
    id: String(s.id ?? s.step_id ?? `step-${i}`),
    name: String(s.step_name ?? s.name ?? `Step ${i + 1}`),
    type: String(s.step_type ?? "task"),
    status: String(s.status ?? "Not reported"),
    error: (s.error_message as string) ?? (s.errorMessage as string) ?? null,
  }))
}

function dryRunStateFromResponse(res: WorkflowDryRunResponse | null | undefined) {
  if (!res) {
    return {
      steps: null as DryRunStep[] | null,
      errors: [] as string[],
      status: null as string | null,
    }
  }
  const raw = (res.steps ?? []) as Array<Record<string, unknown>>
  return {
    steps: mapDryRunSteps(raw),
    errors: res.errors ?? [],
    status: res.status ?? "Not reported",
  }
}

export function WorkflowIntelligenceDrawer({
  open,
  onClose,
  workflowId,
  isPersisted,
  nodes,
  initialTab = "simulate",
  prefetchedDryRun = null,
}: IntelligenceDrawerProps) {
  const reduced = useReducedMotion()
  const prefetchedDryRunState = dryRunStateFromResponse(prefetchedDryRun)
  const [activeTab, setActiveTab] = useState<DrawerTab>(initialTab)

  // Simulate (digital twin)
  const [simSteps, setSimSteps] = useState<SimulatedStep[] | null>(null)
  const [simRunning, setSimRunning] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)
  const [simStats, setSimStats] = useState<{
    fixtureHits: number | null
    llmPredictions: number | null
    ragReads: number | null
  } | null>(null)

  // Risk scan
  const [alerts, setAlerts] = useState<WorkflowFailureAlert[] | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)

  // Dry run
  const [dryRunSteps, setDryRunSteps] = useState<DryRunStep[] | null>(prefetchedDryRunState.steps)
  const [dryRunErrors, setDryRunErrors] = useState<string[]>(prefetchedDryRunState.errors)
  const [dryRunLoading, setDryRunLoading] = useState(false)
  const [dryRunError, setDryRunError] = useState<string | null>(null)
  const [dryRunStatus, setDryRunStatus] = useState<string | null>(prefetchedDryRunState.status)

  const runSimulation = useCallback(async () => {
    if (!isPersisted) return
    setSimRunning(true)
    setSimSteps(null)
    setSimError(null)
    setSimStats(null)
    try {
      const res: WorkflowDigitalTwinResponse = await workflowsApi.digitalTwin({
        workflow_id: workflowId,
      })
      if (res.errors?.length) setSimError(res.errors.join(" · "))
      setSimSteps(mapDigitalTwinSteps((res.steps ?? []) as Array<Record<string, unknown>>, nodes))
      setSimStats({
        fixtureHits: reportedCount(res.fixtureHits),
        llmPredictions: reportedCount(res.llmPredictions),
        ragReads: reportedCount(res.ragReads),
      })
    } catch (err) {
      setSimError(err instanceof Error ? err.message : "Digital twin simulation failed")
    } finally {
      setSimRunning(false)
    }
  }, [isPersisted, workflowId, nodes])

  const runRiskScan = useCallback(async () => {
    setRiskLoading(true)
    setRiskError(null)
    try {
      if (isPersisted) {
        const scanned = await workflowsApi.scanFailurePredictions(workflowId)
        if (!Array.isArray(scanned.alerts)) throw new Error("Risk scan returned no alert inventory.")
        setAlerts(scanned.alerts)
      } else {
        const res = await workflowsApi.listFailurePredictions({
          workflowId,
          status: "active",
        })
        if (!Array.isArray(res.alerts)) throw new Error("Risk scan returned no alert inventory.")
        setAlerts(res.alerts)
      }
    } catch (err) {
      setRiskError(err instanceof Error ? err.message : "Failed to scan for risks")
      setAlerts([])
    } finally {
      setRiskLoading(false)
    }
  }, [isPersisted, workflowId])

  const runDryRun = useCallback(async () => {
    setDryRunLoading(true)
    setDryRunError(null)
    setDryRunSteps(null)
    setDryRunErrors([])
    setDryRunStatus(null)
    try {
      const res = await workflowsApi.dryRun({ workflow_id: workflowId })
      const mapped = dryRunStateFromResponse(res)
      setDryRunSteps(mapped.steps)
      setDryRunErrors(mapped.errors)
      setDryRunStatus(mapped.status)
    } catch (err) {
      setDryRunError(err instanceof Error ? err.message : "Dry run failed")
    } finally {
      setDryRunLoading(false)
    }
  }, [workflowId])

  const dryRunSuccessful =
    isSuccessfulWorkflowStatus(dryRunStatus) &&
    dryRunErrors.length === 0 &&
    !dryRunSteps?.some((step) => step.error || step.status === "failed")
  const totalPredictedMs = totalSimulationDuration(simSteps)

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <SheetContent
        side="right"
        className="w-full gap-0 p-0 sm:max-w-md [&_[data-slot=button]]:min-h-11"
        aria-describedby="workflow-intelligence-description"
      >
        <SheetTitle className="sr-only">Workflow intelligence</SheetTitle>
        <SheetDescription id="workflow-intelligence-description" className="sr-only">
          Review simulation evidence, risk scan and dry-run results before execution.
        </SheetDescription>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <GitBranch className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold leading-tight text-foreground">
                Workflow intelligence
              </h2>
              <p className="text-xs text-muted-foreground">Predict before you ship</p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border px-2 py-2">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {!isPersisted && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-[color:var(--status-pending)]/30 bg-[color:var(--status-pending)]/10 p-3 text-xs text-[color:var(--status-pending)]">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                This is an unsaved draft. Save the workflow to run a live risk scan and dry run
                against the backend.
              </span>
            </div>
          )}

          {/* SIMULATE */}
          {activeTab === "simulate" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-medium text-primary">
                    <Beaker className="h-3 w-3" />
                    Simulated
                  </span>
                  <span>Digital twin · no side effects</span>
                </div>
              </div>

              {simRunning && (
                <div className="space-y-2">
                  {Array.from({ length: Math.max(nodes.length, 3) }).map((_, i) => (
                    <div
                      key={i}
                      className="h-14 animate-pulse rounded-lg border border-border bg-muted/40"
                    />
                  ))}
                </div>
              )}

              {!simRunning && simError && (
                <EmptyState
                  icon={ServerCrash}
                  title="Simulation failed"
                  body={simError}
                  actionLabel={isPersisted ? "Retry" : undefined}
                  onAction={isPersisted ? runSimulation : undefined}
                  tone="error"
                />
              )}

              {!simRunning && !simError && !simSteps && (
                <EmptyState
                  icon={Beaker}
                  title="Predict the run timeline"
                  illustration="spot-schedules"
                  body="Estimate how long each step will take, using sample data from your connectors and past runs. Nothing is executed."
                  actionLabel={isPersisted && nodes.length ? "Run timing simulation" : undefined}
                  onAction={isPersisted && nodes.length ? runSimulation : undefined}
                  disabledHint={
                    !isPersisted
                      ? "Save the workflow to simulate"
                      : nodes.length
                        ? undefined
                        : "Add steps to the canvas first"
                  }
                />
              )}

              {!simRunning && !simError && simSteps && (
                <>
                  <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      Simulation elapsed
                    </div>
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {formatMs(totalPredictedMs)}
                    </span>
                  </div>
                  {simStats && (
                    <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                      <Badge variant="secondary">
                        Sample data {simStats.fixtureHits ?? "Not reported"}
                      </Badge>
                      <Badge variant="secondary">
                        AI estimates {simStats.llmPredictions ?? "Not reported"}
                      </Badge>
                      {simStats.ragReads !== null && simStats.ragReads > 0 && (
                        <Badge variant="secondary">
                          Knowledge lookups {simStats.ragReads ?? "Not reported"}
                        </Badge>
                      )}
                    </div>
                  )}
                  <ol className="relative space-y-2 pl-4">
                    <span
                      className="absolute bottom-2 left-[7px] top-2 w-px bg-border"
                      aria-hidden
                    />
                    {simSteps.map((step, i) => (
                      <motion.li
                        key={step.id}
                        initial={reduced ? false : { opacity: 0, x: 8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="relative rounded-lg border border-border bg-card px-3 py-2"
                      >
                        <span
                          className={cn(
                            "absolute -left-[9px] top-4 h-2.5 w-2.5 rounded-full ring-2 ring-card",
                            step.source === "fixture" ? "bg-primary" : "bg-chart-2",
                          )}
                          aria-hidden
                        />
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium text-foreground">
                            {step.name}
                          </span>
                          <span className="shrink-0 font-mono text-xs text-muted-foreground">
                            {formatMs(step.predictedMs)}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <Badge
                            variant="outline"
                            className={cn(
                              "gap-1 px-1.5 py-0 text-[10px]",
                              step.source === "fixture"
                                ? "border-primary/30 text-primary"
                                : "border-chart-2/40 text-chart-2",
                            )}
                          >
                            {step.source === "fixture" ? (
                              <Database className="h-2.5 w-2.5" />
                            ) : (
                              <Cpu className="h-2.5 w-2.5" />
                            )}
                            {step.source === "fixture" ? "Sample" : "Estimate"}
                          </Badge>
                          <span className="truncate text-[11px] text-muted-foreground">
                            {step.note}
                          </span>
                        </div>
                      </motion.li>
                    ))}
                  </ol>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full gap-2"
                    onClick={runSimulation}
                  >
                    <Beaker className="h-3.5 w-3.5" />
                    Re-run simulation
                  </Button>
                </>
              )}
            </div>
          )}

          {/* RISK SCAN */}
          {activeTab === "risk" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Zap className="h-3.5 w-3.5" />
                Predictive failure alerts from historical runs
              </div>

              {riskLoading && (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-16 animate-pulse rounded-lg border border-border bg-muted/40"
                    />
                  ))}
                </div>
              )}

              {!riskLoading && riskError && (
                <EmptyState
                  icon={ServerCrash}
                  title="Couldn't scan for risks"
                  body={riskError}
                  actionLabel="Retry"
                  onAction={runRiskScan}
                  tone="error"
                />
              )}

              {!riskLoading && !riskError && alerts === null && (
                <EmptyState
                  icon={ShieldAlert}
                  title="Scan for failure risks"
                  illustration="spot-governance"
                  body="Check this workflow against predicted failure patterns before running it in production."
                  actionLabel={isPersisted ? "Run risk scan" : undefined}
                  onAction={isPersisted ? runRiskScan : undefined}
                  disabledHint={isPersisted ? undefined : "Save the workflow to scan"}
                />
              )}

              {!riskLoading && !riskError && alerts !== null && alerts.length === 0 && (
                <div className="flex flex-col items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-4 py-8 text-center">
                  <Illustration name="moment-all-clear" width={140} />
                  <p className="text-sm font-medium text-foreground">No risks detected</p>
                  <p className="text-xs text-muted-foreground">
                    This workflow shows no predicted failure patterns.
                  </p>
                  <Button variant="ghost" size="sm" className="mt-1 gap-2" onClick={runRiskScan}>
                    <Zap className="h-3.5 w-3.5" />
                    Re-scan
                  </Button>
                </div>
              )}

              {!riskLoading && !riskError && alerts && alerts.length > 0 && (
                <div className="space-y-3">
                  {(["critical", "high", "medium", "low"] as const).map((sev) => {
                    const group = alerts.filter((a) => a.severity === sev)
                    if (group.length === 0) return null
                    const style = SEVERITY_STYLES[sev]
                    return (
                      <div key={sev} className="space-y-2">
                        <div className="flex items-center gap-2">
                          <span className={cn("h-2 w-2 rounded-full", style.dot)} aria-hidden />
                          <span className={cn("text-xs font-semibold", style.text)}>
                            {style.label}
                          </span>
                          <span className="text-xs text-muted-foreground">({group.length})</span>
                        </div>
                        {group.map((alert, i) => (
                          <motion.div
                            key={alert.id}
                            initial={reduced ? false : { opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{
                              duration: reduced ? 0 : 0.18,
                              delay: reduced ? 0 : i * 0.04,
                            }}
                            className={cn("rounded-lg border p-3", style.border, style.bg)}
                          >
                            <div className="flex items-start gap-2">
                              <AlertTriangle
                                className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", style.text)}
                              />
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-foreground">{alert.title}</p>
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                  {alert.message}
                                </p>
                                <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                                  <span className="font-mono">
                                    {Math.round(alert.confidence * 100)}% confidence
                                  </span>
                                  {alert.alertType && (
                                    <>
                                      <span aria-hidden>·</span>
                                      <span>{alert.alertType.replace(/_/g, " ")}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* DRY RUN */}
          {activeTab === "dryrun" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1 rounded-full border border-chart-2/40 bg-chart-2/10 px-2 py-0.5 font-medium text-chart-2">
                  <Play className="h-3 w-3" />
                  Validated
                </span>
                Executes against the engine with no external writes
              </div>

              {dryRunLoading && (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-12 animate-pulse rounded-lg border border-border bg-muted/40"
                    />
                  ))}
                </div>
              )}

              {!dryRunLoading && dryRunError && (
                <EmptyState
                  icon={ServerCrash}
                  title="Dry run failed"
                  body={dryRunError}
                  actionLabel="Retry"
                  onAction={runDryRun}
                  tone="error"
                />
              )}

              {!dryRunLoading && !dryRunError && !dryRunSteps && (
                <EmptyState
                  icon={Play}
                  title="Validate without side effects"
                  illustration="spot-workflows"
                  body="Run the workflow through the engine to validate configuration and surface errors before a live run."
                  actionLabel={isPersisted ? "Start dry run" : undefined}
                  onAction={isPersisted ? runDryRun : undefined}
                  disabledHint={isPersisted ? undefined : "Save the workflow to dry run"}
                />
              )}

              {!dryRunLoading && !dryRunError && dryRunSteps && (
                <>
                  <div
                    className={cn(
                      "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                      dryRunSuccessful
                        ? "border-success/30 bg-success/10 text-success"
                        : "border-destructive/40 bg-destructive/10 text-destructive",
                    )}
                  >
                    {dryRunSuccessful ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <span className="font-medium">
                      {dryRunSuccessful
                        ? `Validation passed${dryRunStatus ? ` · ${dryRunStatus}` : ""}`
                        : dryRunErrors.length > 0
                          ? `${dryRunErrors.length} issue${dryRunErrors.length > 1 ? "s" : ""} found`
                          : `Validation status · ${dryRunStatus ?? "Not reported"}`}
                    </span>
                  </div>

                  {dryRunErrors.length > 0 && (
                    <ul className="space-y-1">
                      {dryRunErrors.map((e, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-1.5 text-xs text-destructive"
                        >
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                          {e}
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="space-y-1.5">
                    {dryRunSteps.map((step, i) => {
                      const failed = step.status === "failed" || !!step.error
                      return (
                        <motion.div
                          key={step.id}
                          initial={reduced ? false : { opacity: 0, x: 8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{
                            duration: reduced ? 0 : 0.18,
                            delay: reduced ? 0 : i * 0.04,
                          }}
                          className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2"
                        >
                          {failed ? (
                            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                          ) : isSuccessfulWorkflowStatus(step.status) ? (
                            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[color:var(--g-brand)]" />
                          ) : (
                            <Info className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          )}
                          <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                            {step.name}
                          </span>
                          <Badge variant="outline" className="shrink-0 px-1.5 py-0 text-[10px]">
                            {step.status}
                          </Badge>
                        </motion.div>
                      )
                    })}
                  </div>

                  <Button variant="outline" size="sm" className="w-full gap-2" onClick={runDryRun}>
                    <Play className="h-3.5 w-3.5" />
                    Re-run dry run
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function EmptyState({
  icon: Icon,
  illustration,
  title,
  body,
  actionLabel,
  onAction,
  disabledHint,
  tone = "default",
}: {
  icon: typeof Beaker
  /** Library scene shown instead of the icon tile; error tone defaults to moment-error. */
  illustration?: IllustrationName
  title: string
  body: string
  actionLabel?: string
  onAction?: () => void
  disabledHint?: string
  tone?: "default" | "error"
}) {
  const scene = illustration ?? (tone === "error" ? "moment-error" : undefined)
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-4 py-10 text-center">
      {scene ? (
        <Illustration name={scene} width={140} />
      ) : (
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="h-5 w-5" />
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{body}</p>
      </div>
      {actionLabel && onAction && (
        <Button size="sm" className="gap-2" onClick={onAction}>
          <ChevronRight className="h-3.5 w-3.5" />
          {actionLabel}
        </Button>
      )}
      {!actionLabel && disabledHint && (
        <p className="text-[11px] italic text-muted-foreground">{disabledHint}</p>
      )}
    </div>
  )
}
