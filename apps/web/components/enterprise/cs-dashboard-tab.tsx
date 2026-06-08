"use client"

import { useCallback, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Lightbulb,
  Plug,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  X,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { enterpriseApi, workflowsApi } from "@/lib/api"
import type {
  IntegrationHealthDimension,
  IntegrationHealthGrade,
  IntegrationHealthScore,
  IntegrationHealthSnapshot,
  IntegrationSuggestion,
  WorkflowFailureAlert,
} from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

const LOOKBACK_DAYS = 30

const DIMENSION_LABELS: Record<string, string> = {
  connectorsLive: "Connectors live",
  workflowSuccessRate: "Workflow success",
  agentUtilization: "Agent utilization",
  approvalLatency: "Approval latency",
}

function gradeBadgeClass(grade: IntegrationHealthGrade): string {
  if (grade === "healthy") return "border-success/30 bg-success/10 text-success"
  if (grade === "at_risk") return "border-amber-500/30 bg-amber-500/10 text-amber-500"
  return "border-destructive/30 bg-destructive/10 text-destructive"
}

function gradeLabel(grade: IntegrationHealthGrade): string {
  if (grade === "healthy") return "Healthy"
  if (grade === "at_risk") return "At risk"
  return "Critical"
}

function scoreRingColor(score: number): string {
  if (score >= 85) return "var(--success)"
  if (score >= 65) return "#f59e0b"
  return "var(--destructive)"
}

function HealthScoreHero({ health }: { health: IntegrationHealthScore }) {
  const ringPct = Math.min(100, Math.max(0, health.score))
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-5">
          <div
            className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(${scoreRingColor(health.score)} ${ringPct * 3.6}deg, var(--secondary) 0deg)`,
            }}
            aria-hidden
          >
            <div className="flex h-[5.5rem] w-[5.5rem] flex-col items-center justify-center rounded-full bg-card">
              <span className="text-3xl font-semibold tabular-nums text-foreground">{health.score}</span>
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Score</span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-foreground">Integration health</h3>
              <Badge variant="outline" className={cn("capitalize", gradeBadgeClass(health.grade))}>
                {gradeLabel(health.grade)}
              </Badge>
            </div>
            <p className="max-w-md text-sm text-muted-foreground text-pretty">
              Composite score from connectors, workflow success, agent utilization, and approval latency over the last{" "}
              {health.lookbackDays} days.
            </p>
            <p className="text-xs text-muted-foreground/70">
              Updated {new Date(health.computedAt).toLocaleString()}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function DimensionBar({ name, dim }: { name: string; dim: IntegrationHealthDimension }) {
  const label = DIMENSION_LABELS[name] ?? dim.label ?? name
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{dim.score}/100</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-secondary">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-300",
            dim.score >= 85 ? "bg-success" : dim.score >= 65 ? "bg-amber-500" : "bg-destructive",
          )}
          style={{ width: `${dim.score}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{dim.summary}</p>
    </div>
  )
}

function HealthTrendChart({ snapshots }: { snapshots: IntegrationHealthSnapshot[] }) {
  const points = useMemo(() => {
    const ordered = [...snapshots].reverse()
    if (ordered.length < 2) return null
    const w = 280
    const h = 64
    const scores = ordered.map((s) => s.score)
    const max = 100
    const min = 0
    const step = w / Math.max(1, scores.length - 1)
    const d = scores
      .map((score, i) => {
        const x = i * step
        const y = h - ((score - min) / (max - min)) * h
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`
      })
      .join(" ")
    return { d, w, h, latest: scores[scores.length - 1], delta: scores[scores.length - 1] - scores[0] }
  }, [snapshots])

  if (!points) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        Record snapshots to see health trends over time.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">Trend ({snapshots.length} snapshots)</span>
        <span
          className={cn(
            "font-medium tabular-nums",
            points.delta >= 0 ? "text-success" : "text-destructive",
          )}
        >
          {points.delta >= 0 ? "+" : ""}
          {points.delta} pts
        </span>
      </div>
      <svg viewBox={`0 0 ${points.w} ${points.h}`} className="h-16 w-full" preserveAspectRatio="none" aria-hidden>
        <path d={points.d} fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinecap="round" />
      </svg>
    </div>
  )
}

function SuggestionCard({
  suggestion,
  onDismiss,
  dismissing,
}: {
  suggestion: IntegrationSuggestion
  onDismiss: (id: string) => void
  dismissing: string | null
}) {
  const Icon =
    suggestion.suggestionType === "connect_connector"
      ? Plug
      : suggestion.suggestionType === "install_department_pack"
        ? Lightbulb
        : TrendingUp

  const installHref =
    suggestion.suggestionType === "install_department_pack" ? "/marketplace/role-packs" : null

  return (
    <div className="flex gap-3 rounded-lg border border-border bg-card/50 p-4">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10">
        <Icon className="h-4 w-4 text-primary" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="text-sm font-medium text-foreground">{suggestion.title}</p>
          <Badge variant="outline" className="shrink-0 tabular-nums">
            P{suggestion.priority}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground text-pretty">{suggestion.message}</p>
        <div className="flex flex-wrap gap-2 pt-1">
          {installHref ? (
            <Button variant="outline" size="sm" asChild>
              <Link href={installHref}>Install department pack</Link>
            </Button>
          ) : null}
          {suggestion.connectorType ? (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/connectors?type=${suggestion.connectorType}`}>Connectors</Link>
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            disabled={dismissing === suggestion.id}
            onClick={() => onDismiss(suggestion.id)}
          >
            {dismissing === suggestion.id ? "Dismissing…" : "Dismiss"}
          </Button>
        </div>
      </div>
    </div>
  )
}

function FailureAlertRow({
  alert,
  onDismiss,
  dismissing,
}: {
  alert: WorkflowFailureAlert
  onDismiss: (id: string) => void
  dismissing: string | null
}) {
  const severityClass =
    alert.severity === "critical"
      ? "text-destructive"
      : alert.severity === "high"
        ? "text-amber-500"
        : "text-muted-foreground"

  return (
    <div className="flex gap-3 rounded-lg border border-border/80 p-3">
      <ShieldAlert className={cn("mt-0.5 h-4 w-4 shrink-0", severityClass)} aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-foreground">{alert.title}</p>
          <Badge variant="outline" className="capitalize">
            {alert.severity}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{alert.message}</p>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-muted-foreground"
          disabled={dismissing === alert.id}
          onClick={() => onDismiss(alert.id)}
        >
          Dismiss
        </Button>
      </div>
    </div>
  )
}

export function CsDashboardTab() {
  const [busy, setBusy] = useState<string | null>(null)
  const [dismissingFailureId, setDismissingFailureId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { data: health, isLoading: healthLoading, mutate: mutateHealth } = useSWR(
    "enterprise-integration-health",
    () => enterpriseApi.getIntegrationHealth(LOOKBACK_DAYS),
    { revalidateOnFocus: false },
  )

  const { data: history, mutate: mutateHistory } = useSWR(
    "enterprise-integration-health-history",
    () => enterpriseApi.getIntegrationHealthHistory(30),
    { revalidateOnFocus: false },
  )

  const { data: suggestionsData, mutate: mutateSuggestions } = useSWR(
    "enterprise-integration-suggestions",
    () => enterpriseApi.getIntegrationSuggestions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  const { data: failureData, mutate: mutateFailures } = useSWR(
    "workflow-failure-predictions",
    () => workflowsApi.listFailurePredictions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(null), 3000)
  }, [])

  const refreshAll = useCallback(async () => {
    await Promise.all([mutateHealth(), mutateHistory(), mutateSuggestions(), mutateFailures()])
  }, [mutateHealth, mutateHistory, mutateSuggestions, mutateFailures])

  const recordSnapshot = async () => {
    setBusy("snapshot")
    try {
      await enterpriseApi.recordIntegrationHealthSnapshot(LOOKBACK_DAYS)
      await Promise.all([mutateHealth(), mutateHistory()])
      showToast("Health snapshot recorded")
    } catch {
      showToast("Failed to record snapshot")
    } finally {
      setBusy(null)
    }
  }

  const scanSuggestions = async () => {
    setBusy("scan")
    try {
      await enterpriseApi.scanIntegrationSuggestions(LOOKBACK_DAYS)
      await mutateSuggestions()
      showToast("Recommendations updated from audit data")
    } catch {
      showToast("Failed to scan audit data")
    } finally {
      setBusy(null)
    }
  }

  const dismissSuggestion = async (id: string) => {
    setBusy(id)
    try {
      await enterpriseApi.dismissIntegrationSuggestion(id)
      await mutateSuggestions()
    } finally {
      setBusy(null)
    }
  }

  const dismissFailure = async (id: string) => {
    setDismissingFailureId(id)
    try {
      await workflowsApi.dismissFailurePrediction(id)
      await mutateFailures()
    } finally {
      setDismissingFailureId(null)
    }
  }

  if (healthLoading) return <TabSkeleton rows={4} />

  const suggestions = suggestionsData?.suggestions ?? []
  const failures = failureData?.alerts ?? []
  const snapshots = history?.snapshots ?? []
  const dimensions = health?.dimensions ?? {}
  const risks = health?.risks ?? []

  return (
    <div className="space-y-6">
      {toast ? (
        <div
          className="flex items-center justify-between gap-2 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-foreground"
          role="status"
        >
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
            {toast}
          </span>
          <button type="button" onClick={() => setToast(null)} aria-label="Dismiss notification">
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Customer success view — integration health, recommendations, and workflow risk alerts.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" disabled={!!busy} onClick={() => void refreshAll()}>
            <RefreshCw className={cn("mr-1.5 h-4 w-4", busy === "refresh" && "animate-spin")} aria-hidden />
            Refresh
          </Button>
          <Button variant="outline" size="sm" disabled={!!busy} onClick={() => void recordSnapshot()}>
            <Camera className="mr-1.5 h-4 w-4" aria-hidden />
            Record snapshot
          </Button>
        </div>
      </div>

      {health ? <HealthScoreHero health={health} /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" aria-hidden />
              <CardTitle className="text-base">Health dimensions</CardTitle>
            </div>
            <CardDescription>Four weighted signals that drive the composite score.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(dimensions).map(([key, dim]) => (
              <DimensionBar key={key} name={key} dim={dim} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" aria-hidden />
              <CardTitle className="text-base">Score history</CardTitle>
            </div>
            <CardDescription>Snapshots for CS trend reviews and QBRs.</CardDescription>
          </CardHeader>
          <CardContent>
            <HealthTrendChart snapshots={snapshots} />
          </CardContent>
        </Card>
      </div>

      {risks.length > 0 ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
              <CardTitle className="text-base">Active risks</CardTitle>
            </div>
            <CardDescription>Dimensions scoring below 70 need CS follow-up.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {risks.map((risk) => (
              <div
                key={risk.dimension}
                className="flex items-start justify-between gap-3 rounded-md border border-border/60 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium text-foreground">
                    {DIMENSION_LABELS[risk.dimension] ?? risk.dimension}
                  </p>
                  <p className="text-muted-foreground">{risk.summary}</p>
                </div>
                <Badge variant={risk.severity === "high" ? "destructive" : "outline"}>
                  {risk.score}/100
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div>
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" aria-hidden />
              <CardTitle className="text-base">Integration recommendations</CardTitle>
            </div>
            <CardDescription>
              Suggested connectors and workflows from audit usage patterns.
            </CardDescription>
          </div>
          <Button size="sm" disabled={!!busy} onClick={() => void scanSuggestions()}>
            Scan audit data
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {suggestions.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No open recommendations. Run a scan after agents and operators use connectors.
            </p>
          ) : (
            suggestions.map((s) => (
              <SuggestionCard
                key={s.id}
                suggestion={s}
                onDismiss={(id) => void dismissSuggestion(id)}
                dismissing={busy}
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-destructive" aria-hidden />
            <CardTitle className="text-base">Workflow failure predictions</CardTitle>
          </div>
          <CardDescription>
            Pre-failure alerts from auth expiry, rate limits, and missing scopes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {failures.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No open workflow failure alerts. Scan workflows from the workflow builder to generate predictions.
            </p>
          ) : (
            failures.map((alert) => (
              <FailureAlertRow
                key={alert.id}
                alert={alert}
                onDismiss={(id) => void dismissFailure(id)}
                dismissing={dismissingFailureId}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
