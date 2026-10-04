"use client"

import { useCallback, useState } from "react"
import { useReducedMotion } from "framer-motion"
import {
  formatSimulationDuration as formatMs,
  simulationDuration,
  totalSimulationDuration,
  reportedCount,
} from "@/lib/workflow-evidence"
import { motion } from "framer-motion"
import {
  Beaker,
  ShieldAlert,
  Clock,
  Cpu,
  Database,
  Loader2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { workflowsApi } from "@/lib/api"
import { STATUS } from "@/lib/design-system"
import type { WorkflowDigitalTwinResponse, WorkflowFailureAlert } from "@/types/api"
import type { IntelligenceDrawerNode } from "@/components/workflows/intelligence-drawer"

type PanelTab = "timing" | "risk"

const SEVERITY_STYLES: Record<string, { badge: string; label: string }> = {
  critical: { badge: STATUS.failed, label: "Critical" },
  high: { badge: STATUS.rejected, label: "High" },
  medium: { badge: STATUS.pending, label: "Medium" },
  low: { badge: STATUS.idle, label: "Low" },
}

function mapDigitalTwinSteps(
  rawSteps: Array<Record<string, unknown>>,
  canvasNodes: IntelligenceDrawerNode[],
) {
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

export function WorkflowPreRunPanel({
  workflowId,
  nodes,
  className,
}: {
  workflowId: string
  nodes: IntelligenceDrawerNode[]
  className?: string
}) {
  const reduced = useReducedMotion()
  const [tab, setTab] = useState<PanelTab>("timing")
  const [simSteps, setSimSteps] = useState<ReturnType<typeof mapDigitalTwinSteps> | null>(null)
  const [simRunning, setSimRunning] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)
  const [simStats, setSimStats] = useState<{
    fixtureHits: number | null
    llmPredictions: number | null
    ragReads: number | null
  } | null>(null)
  const [alerts, setAlerts] = useState<WorkflowFailureAlert[] | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)

  const runTimingEstimate = useCallback(async () => {
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
      setSimError(err instanceof Error ? err.message : "Timing estimate failed")
    } finally {
      setSimRunning(false)
    }
  }, [workflowId, nodes])

  const runRiskScan = useCallback(async () => {
    setRiskLoading(true)
    setRiskError(null)
    try {
      const res = await workflowsApi.scanFailurePredictions(workflowId)
      if (!Array.isArray(res.alerts)) throw new Error("Risk scan returned no alert inventory.")
      setAlerts(res.alerts)
    } catch (err) {
      setRiskError(err instanceof Error ? err.message : "Failure scan failed")
    } finally {
      setRiskLoading(false)
    }
  }, [workflowId])

  const totalPredictedMs = totalSimulationDuration(simSteps)

  return (
    <Card className={cn("border-border/80", className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Beaker className="h-4 w-4 text-muted-foreground" />
              Before you run
            </CardTitle>
            <CardDescription>
              Safe checks only — nothing executes against production connectors. Use Run in
              production below when you are ready to go live.
            </CardDescription>
          </div>
          <div className="flex gap-1 rounded-lg border border-border p-0.5">
            {(
              [
                {
                  id: "timing" as const,
                  label: "Timing evidence",
                  icon: Clock,
                },
                { id: "risk" as const, label: "Risk scan", icon: ShieldAlert },
              ] as const
            ).map((item) => (
              <Button
                key={item.id}
                size="sm"
                variant={tab === item.id ? "secondary" : "ghost"}
                className="h-8 gap-1.5"
                onClick={() => setTab(item.id)}
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {tab === "timing" ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={simRunning || nodes.length === 0}
                onClick={() => void runTimingEstimate()}
              >
                {simRunning ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Clock className="h-4 w-4 mr-2" />
                )}
                Run timing simulation
              </Button>
              {nodes.length === 0 ? (
                <span className="text-xs text-muted-foreground">
                  Add steps in the builder first.
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">
                  Estimated from past runs and sample data. Nothing is executed.
                </span>
              )}
            </div>
            {simError ? (
              <p className="text-sm text-destructive flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {simError}
              </p>
            ) : null}
            {!simRunning && simSteps ? (
              <>
                <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
                  <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    Simulation elapsed
                  </span>
                  <span className="font-mono text-sm font-semibold">
                    {formatMs(totalPredictedMs)}
                  </span>
                </div>
                {simStats ? (
                  <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline">
                      Sample data {simStats.fixtureHits ?? "Not reported"}
                    </Badge>
                    <Badge variant="outline">
                      AI estimates {simStats.llmPredictions ?? "Not reported"}
                    </Badge>
                    {simStats.ragReads !== null && simStats.ragReads > 0 ? (
                      <Badge variant="outline">
                        Knowledge lookups {simStats.ragReads ?? "Not reported"}
                      </Badge>
                    ) : null}
                  </div>
                ) : null}
                <ol className="space-y-2">
                  {simSteps.map((step, i) => (
                    <motion.li
                      key={step.id}
                      initial={reduced ? false : { opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        duration: reduced ? 0 : 0.18,
                        delay: reduced ? 0 : i * 0.04,
                      }}
                      className="rounded-lg border border-border/70 px-3 py-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate">{step.name}</span>
                        <span className="font-mono text-xs text-muted-foreground shrink-0">
                          {formatMs(step.predictedMs)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                        {step.source === "fixture" ? (
                          <Database className="h-3 w-3" />
                        ) : (
                          <Cpu className="h-3 w-3" />
                        )}
                        {step.note}
                      </div>
                    </motion.li>
                  ))}
                </ol>
              </>
            ) : null}
          </>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={riskLoading}
                onClick={() => void runRiskScan()}
              >
                {riskLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Scan for failure risks
              </Button>
              <span className="text-xs text-muted-foreground">
                Prediction only — does not execute steps.
              </span>
            </div>
            {riskError ? (
              <p className="text-sm text-destructive flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {riskError}
              </p>
            ) : null}
            {alerts && alerts.length === 0 && !riskLoading ? (
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                No open failure predictions for this workflow.
              </p>
            ) : null}
            {alerts && alerts.length > 0 ? (
              <ul className="space-y-2">
                {alerts.map((alert) => {
                  const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.medium
                  return (
                    <li
                      key={alert.id}
                      className="rounded-lg border border-border/70 px-3 py-2 space-y-1"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium">{alert.title}</p>
                        <Badge
                          variant="outline"
                          className={cn("shrink-0 text-[10px]", style.badge)}
                        >
                          {style.label}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{alert.message}</p>
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}
