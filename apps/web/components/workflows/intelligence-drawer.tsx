"use client"

import { useState, useCallback, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Sparkles,
  X,
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
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { workflowsApi } from "@/lib/api"
import type { WorkflowFailureAlert } from "@/types/api"

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
  /** Increment to trigger a dry run when the drawer opens. */
  dryRunTrigger?: number
}

interface SimulatedStep {
  id: string
  name: string
  type: string
  predictedMs: number
  source: "fixture" | "llm"
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
  { id: "simulate", label: "Simulate", icon: Beaker },
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
    dot: "bg-orange-500",
    text: "text-orange-500",
    border: "border-orange-500/40",
    bg: "bg-orange-500/10",
    label: "High",
  },
  medium: {
    dot: "bg-amber-500",
    text: "text-amber-500",
    border: "border-amber-500/40",
    bg: "bg-amber-500/10",
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

// Deterministic per-node-type simulation heuristics. The digital-twin engine
// uses connector fixtures where available and falls back to LLM estimation.
const TYPE_PROFILE: Record<string, { ms: number; source: "fixture" | "llm"; note: string }> = {
  source: { ms: 480, source: "fixture", note: "Connector fixture replay" },
  connector: { ms: 620, source: "fixture", note: "Connector fixture replay" },
  task: { ms: 350, source: "fixture", note: "Deterministic handler" },
  agent: { ms: 2400, source: "llm", note: "LLM estimate (model latency)" },
  approval: { ms: 0, source: "fixture", note: "Waits for human approval" },
  decision: { ms: 120, source: "fixture", note: "Branch evaluation" },
}

function profileFor(type: string) {
  return TYPE_PROFILE[type] ?? { ms: 500, source: "llm" as const, note: "LLM estimate" }
}

function formatMs(ms: number): string {
  if (ms === 0) return "—"
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function WorkflowIntelligenceDrawer({
  open,
  onClose,
  workflowId,
  isPersisted,
  nodes,
  initialTab,
  dryRunTrigger = 0,
}: IntelligenceDrawerProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>(initialTab ?? "simulate")

  // Simulate
  const [simSteps, setSimSteps] = useState<SimulatedStep[] | null>(null)
  const [simRunning, setSimRunning] = useState(false)

  // Risk scan
  const [alerts, setAlerts] = useState<WorkflowFailureAlert[] | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)

  // Dry run
  const [dryRunSteps, setDryRunSteps] = useState<DryRunStep[] | null>(null)
  const [dryRunErrors, setDryRunErrors] = useState<string[]>([])
  const [dryRunLoading, setDryRunLoading] = useState(false)
  const [dryRunError, setDryRunError] = useState<string | null>(null)
  const [dryRunStatus, setDryRunStatus] = useState<string | null>(null)

  const runSimulation = useCallback(() => {
    setSimRunning(true)
    setSimSteps(null)
    // Build a predicted timeline from the canvas graph order.
    window.setTimeout(() => {
      const steps: SimulatedStep[] = nodes.map((n) => {
        const p = profileFor(n.type)
        return {
          id: n.id,
          name: n.name,
          type: n.type,
          predictedMs: p.ms,
          source: p.source,
          note: p.note,
        }
      })
      setSimSteps(steps)
      setSimRunning(false)
    }, 650)
  }, [nodes])

  const runRiskScan = useCallback(async () => {
    setRiskLoading(true)
    setRiskError(null)
    try {
      const res = await workflowsApi.listFailurePredictions({
        workflowId,
        status: "active",
      })
      setAlerts(res.alerts)
    } catch (err) {
      setRiskError(err instanceof Error ? err.message : "Failed to scan for risks")
      setAlerts([])
    } finally {
      setRiskLoading(false)
    }
  }, [workflowId])

  const runDryRun = useCallback(async () => {
    setDryRunLoading(true)
    setDryRunError(null)
    setDryRunSteps(null)
    setDryRunErrors([])
    setDryRunStatus(null)
    try {
      const res = await workflowsApi.dryRun({ workflow_id: workflowId })
      const raw = (res.steps ?? []) as Array<Record<string, unknown>>
      const steps: DryRunStep[] = raw.map((s, i) => ({
        id: String(s.id ?? s.step_id ?? `step-${i}`),
        name: String(s.step_name ?? s.name ?? `Step ${i + 1}`),
        type: String(s.step_type ?? "task"),
        status: String(s.status ?? "completed"),
        error: (s.error_message as string) ?? (s.errorMessage as string) ?? null,
      }))
      setDryRunSteps(steps)
      setDryRunErrors(res.errors ?? [])
      setDryRunStatus(res.status ?? "completed")
    } catch (err) {
      setDryRunError(err instanceof Error ? err.message : "Dry run failed")
    } finally {
      setDryRunLoading(false)
    }
  }, [workflowId])

  useEffect(() => {
    if (open && initialTab) {
      setActiveTab(initialTab)
    }
  }, [open, initialTab])

  useEffect(() => {
    if (open && dryRunTrigger > 0 && isPersisted) {
      void runDryRun()
    }
  }, [open, dryRunTrigger, isPersisted, runDryRun])

  const totalPredictedMs = simSteps?.reduce((sum, s) => sum + s.predictedMs, 0) ?? 0

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Scrim */}
          <motion.div
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            key="intelligence-drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border bg-card shadow-2xl"
            role="dialog"
            aria-label="Workflow intelligence"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold leading-tight text-foreground">
                    Workflow Intelligence
                  </h2>
                  <p className="text-xs text-muted-foreground">Predict before you ship</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose} aria-label="Close">
                <X className="h-4 w-4" />
              </Button>
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
                      "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
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
                <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-600 dark:text-amber-400">
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

                  {!simRunning && !simSteps && (
                    <EmptyState
                      icon={Beaker}
                      title="Predict the run timeline"
                      body="Run a digital-twin simulation to estimate per-step duration using connector fixtures and LLM latency estimates."
                      actionLabel={nodes.length ? "Simulate run" : undefined}
                      onAction={nodes.length ? runSimulation : undefined}
                      disabledHint={nodes.length ? undefined : "Add steps to the canvas first"}
                    />
                  )}

                  {!simRunning && simSteps && (
                    <>
                      <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Clock className="h-3.5 w-3.5" />
                          Predicted total
                        </div>
                        <span className="font-mono text-sm font-semibold text-foreground">
                          {formatMs(totalPredictedMs)}
                        </span>
                      </div>
                      <ol className="relative space-y-2 pl-4">
                        <span className="absolute bottom-2 left-[7px] top-2 w-px bg-border" aria-hidden />
                        {simSteps.map((step, i) => (
                          <motion.li
                            key={step.id}
                            initial={{ opacity: 0, x: 8 }}
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
                                {step.source === "fixture" ? "Fixture" : "LLM"}
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
                      body="Check this workflow against predicted failure patterns before running it in production."
                      actionLabel={isPersisted ? "Run risk scan" : undefined}
                      onAction={isPersisted ? runRiskScan : undefined}
                      disabledHint={isPersisted ? undefined : "Save the workflow to scan"}
                    />
                  )}

                  {!riskLoading && !riskError && alerts !== null && alerts.length === 0 && (
                    <div className="flex flex-col items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-8 text-center">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500" />
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
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.04 }}
                                className={cn("rounded-lg border p-3", style.border, style.bg)}
                              >
                                <div className="flex items-start gap-2">
                                  <AlertTriangle className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", style.text)} />
                                  <div className="min-w-0">
                                    <p className="text-sm font-medium text-foreground">{alert.title}</p>
                                    <p className="mt-0.5 text-xs text-muted-foreground">{alert.message}</p>
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
                          dryRunErrors.length === 0
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "border-destructive/40 bg-destructive/10 text-destructive",
                        )}
                      >
                        {dryRunErrors.length === 0 ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <AlertTriangle className="h-4 w-4" />
                        )}
                        <span className="font-medium">
                          {dryRunErrors.length === 0
                            ? `Validation passed${dryRunStatus ? ` · ${dryRunStatus}` : ""}`
                            : `${dryRunErrors.length} issue${dryRunErrors.length > 1 ? "s" : ""} found`}
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
                              initial={{ opacity: 0, x: 8 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: i * 0.04 }}
                              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2"
                            >
                              {failed ? (
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                              ) : (
                                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
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
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

function EmptyState({
  icon: Icon,
  title,
  body,
  actionLabel,
  onAction,
  disabledHint,
  tone = "default",
}: {
  icon: typeof Beaker
  title: string
  body: string
  actionLabel?: string
  onAction?: () => void
  disabledHint?: string
  tone?: "default" | "error"
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-4 py-10 text-center">
      <div
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-full",
          tone === "error" ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground",
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
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
