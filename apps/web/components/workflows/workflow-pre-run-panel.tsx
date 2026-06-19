"use client"

import { useCallback, useState } from "react"
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
import type { WorkflowDigitalTwinResponse, WorkflowFailureAlert } from "@/types/api"
import type { IntelligenceDrawerNode } from "@/components/workflows/intelligence-drawer"

type PanelTab = "simulate" | "risk"

const SEVERITY_STYLES: Record<string, { badge: string; label: string }> = {
  critical: { badge: "border-destructive/40 text-destructive bg-destructive/10", label: "Critical" },
  high: { badge: "border-orange-500/40 text-orange-500 bg-orange-500/10", label: "High" },
  medium: { badge: "border-amber-500/40 text-amber-600 bg-amber-500/10", label: "Medium" },
  low: { badge: "border-border text-muted-foreground", label: "Low" },
}

const TYPE_PROFILE: Record<string, { ms: number; source: "fixture" | "llm"; note: string }> = {
  source: { ms: 480, source: "fixture", note: "Connector fixture replay" },
  connector: { ms: 620, source: "fixture", note: "Connector fixture replay" },
  task: { ms: 350, source: "fixture", note: "Deterministic handler" },
  agent: { ms: 2400, source: "llm", note: "LLM estimate" },
  approval: { ms: 0, source: "fixture", note: "Waits for human approval" },
  decision: { ms: 120, source: "fixture", note: "Branch evaluation" },
}

function formatMs(ms: number): string {
  if (ms === 0) return "—"
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
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
    const source: "fixture" | "llm" =
      rawSource === "fixture" || rawSource === "live_read" ? "fixture" : "llm"
    const fallback = TYPE_PROFILE[nodeType] ?? { ms: 500, source: "llm" as const, note: "LLM estimate" }
    let predictedMs = 0
    const startedAt = step.started_at ?? step.startedAt
    const completedAt = step.completed_at ?? step.completedAt
    if (startedAt && completedAt) {
      predictedMs = Math.max(
        0,
        new Date(String(completedAt)).getTime() - new Date(String(startedAt)).getTime(),
      )
    }
    if (predictedMs === 0) predictedMs = fallback.ms
    return {
      id: stepId,
      name: canvasNode?.name ?? String(step.step_name ?? step.stepName ?? `Step ${index + 1}`),
      type: nodeType,
      predictedMs,
      source,
      note: fallback.note,
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
  const [tab, setTab] = useState<PanelTab>("simulate")
  const [simSteps, setSimSteps] = useState<ReturnType<typeof mapDigitalTwinSteps> | null>(null)
  const [simRunning, setSimRunning] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)
  const [simStats, setSimStats] = useState<{ fixtureHits: number; llmPredictions: number; ragReads: number } | null>(
    null,
  )
  const [alerts, setAlerts] = useState<WorkflowFailureAlert[] | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState<string | null>(null)

  const runSimulation = useCallback(async () => {
    setSimRunning(true)
    setSimSteps(null)
    setSimError(null)
    setSimStats(null)
    try {
      const res: WorkflowDigitalTwinResponse = await workflowsApi.digitalTwin({ workflow_id: workflowId })
      setSimSteps(mapDigitalTwinSteps((res.steps ?? []) as Array<Record<string, unknown>>, nodes))
      setSimStats({
        fixtureHits: res.fixtureHits ?? 0,
        llmPredictions: res.llmPredictions ?? 0,
        ragReads: res.ragReads ?? 0,
      })
    } catch (err) {
      setSimError(err instanceof Error ? err.message : "Digital twin simulation failed")
    } finally {
      setSimRunning(false)
    }
  }, [workflowId, nodes])

  const runRiskScan = useCallback(async () => {
    setRiskLoading(true)
    setRiskError(null)
    try {
      const scanned = await workflowsApi.scanFailurePredictions(workflowId)
      setAlerts(scanned.alerts)
    } catch (err) {
      setRiskError(err instanceof Error ? err.message : "Failure prediction scan failed")
      setAlerts([])
    } finally {
      setRiskLoading(false)
    }
  }, [workflowId])

  const totalPredictedMs = simSteps?.reduce((sum, s) => sum + s.predictedMs, 0) ?? 0

  return (
    <Card className={cn("border-primary/20", className)}>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Beaker className="h-4 w-4 text-primary" />
              Pre-run intelligence
            </CardTitle>
            <CardDescription>
              Digital-twin simulate and failure prediction scan before you execute in production.
            </CardDescription>
          </div>
          <div className="flex gap-1 rounded-lg border border-border p-0.5">
            {(
              [
                { id: "simulate" as const, label: "Simulate", icon: Beaker },
                { id: "risk" as const, label: "Failure scan", icon: ShieldAlert },
              ] as const
            ).map((item) => (
              <Button
                key={item.id}
                size="sm"
                variant={tab === item.id ? "default" : "ghost"}
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
        {tab === "simulate" ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={simRunning || nodes.length === 0} onClick={() => void runSimulation()}>
                {simRunning ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Beaker className="h-4 w-4 mr-2" />
                )}
                Simulate run
              </Button>
              {nodes.length === 0 ? (
                <span className="text-xs text-muted-foreground">Add steps in the builder first.</span>
              ) : null}
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
                    Predicted total
                  </span>
                  <span className="font-mono text-sm font-semibold">{formatMs(totalPredictedMs)}</span>
                </div>
                {simStats ? (
                  <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline">Fixtures {simStats.fixtureHits}</Badge>
                    <Badge variant="outline">LLM {simStats.llmPredictions}</Badge>
                    {simStats.ragReads > 0 ? <Badge variant="outline">RAG {simStats.ragReads}</Badge> : null}
                  </div>
                ) : null}
                <ol className="space-y-2">
                  {simSteps.map((step, i) => (
                    <motion.li
                      key={step.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.04 }}
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
              <Button size="sm" disabled={riskLoading} onClick={() => void runRiskScan()}>
                {riskLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Scan for failures
              </Button>
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
                    <li key={alert.id} className="rounded-lg border border-border/70 px-3 py-2 space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium">{alert.title}</p>
                        <Badge variant="outline" className={cn("shrink-0 text-[10px]", style.badge)}>
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
