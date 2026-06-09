"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Lightbulb,
  Plug,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react"
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts"
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
import { StatusBeacon } from "@/components/gravitre/premium-effects"
import { TabSkeleton } from "./enterprise-skeletons"

const LOOKBACK_DAYS = 30

const DIMENSION_LABELS: Record<string, string> = {
  connectorsLive: "Connectors live",
  workflowSuccessRate: "Workflow success",
  agentUtilization: "Agent utilization",
  approvalLatency: "Approval latency",
}

const DIMENSION_ICONS: Record<string, typeof Plug> = {
  connectorsLive: Plug,
  workflowSuccessRate: Activity,
  agentUtilization: Sparkles,
  approvalLatency: CheckCircle2,
}

const SEVERITY_ORDER: WorkflowFailureAlert["severity"][] = ["critical", "high", "medium", "low"]

const SEVERITY_META: Record<
  WorkflowFailureAlert["severity"],
  { label: string; dot: string; text: string; ring: string }
> = {
  critical: { label: "Critical", dot: "bg-destructive", text: "text-destructive", ring: "border-destructive/30 bg-destructive/5" },
  high: { label: "High", dot: "bg-amber-500", text: "text-amber-500", ring: "border-amber-500/30 bg-amber-500/5" },
  medium: { label: "Medium", dot: "bg-primary", text: "text-primary", ring: "border-primary/30 bg-primary/5" },
  low: { label: "Low", dot: "bg-muted-foreground", text: "text-muted-foreground", ring: "border-border bg-card/50" },
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

function gradeBeaconStatus(grade: IntegrationHealthGrade): "active" | "warning" | "error" {
  if (grade === "healthy") return "active"
  if (grade === "at_risk") return "warning"
  return "error"
}

function scoreColor(score: number): string {
  if (score >= 85) return "var(--success)"
  if (score >= 65) return "#f59e0b"
  return "var(--destructive)"
}

function barColor(score: number): string {
  if (score >= 85) return "bg-success"
  if (score >= 65) return "bg-amber-500"
  return "bg-destructive"
}

/* ----------------------------------------------------------------------------
 * Animated score ring — sweeps from 0 to the live score with a count-up label.
 * -------------------------------------------------------------------------- */
function ScoreRing({ score, grade }: { score: number; grade: IntegrationHealthGrade }) {
  const size = 132
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const clamped = Math.min(100, Math.max(0, score))
  const offset = circumference - (clamped / 100) * circumference
  const color = scoreColor(clamped)

  const [display, setDisplay] = useState(0)
  useEffect(() => {
    let frame = 0
    let start = 0
    const duration = 1100
    const tick = (now: number) => {
      if (!start) start = now
      const p = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplay(Math.round(eased * clamped))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [clamped])

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{ background: `radial-gradient(circle, ${color}22 0%, transparent 70%)` }}
        animate={{ opacity: [0.5, 0.9, 0.5], scale: [0.95, 1.05, 0.95] }}
        transition={{ duration: 4, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        aria-hidden
      />
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--secondary)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-semibold tabular-nums text-foreground">{display}</span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{gradeLabel(grade)}</span>
      </div>
    </div>
  )
}

function HealthScoreHero({ health }: { health: IntegrationHealthScore }) {
  return (
    <Card className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, var(--foreground) 1px, transparent 0)",
          backgroundSize: "22px 22px",
        }}
        aria-hidden
      />
      <CardContent className="relative flex flex-col items-center gap-6 p-6 sm:flex-row sm:items-center sm:gap-8">
        <ScoreRing score={health.score} grade={health.grade} />
        <div className="space-y-2.5 text-center sm:text-left">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
            <StatusBeacon status={gradeBeaconStatus(health.grade)} size="md" />
            <h3 className="text-lg font-semibold text-foreground">Integration health</h3>
            <Badge variant="outline" className={cn("capitalize", gradeBadgeClass(health.grade))}>
              {gradeLabel(health.grade)}
            </Badge>
          </div>
          <p className="mx-auto max-w-md text-sm text-muted-foreground text-pretty sm:mx-0">
            Composite score from connectors, workflow success, agent utilization, and approval latency over the last{" "}
            {health.lookbackDays} days.
          </p>
          <p className="text-xs text-muted-foreground/70">
            Updated {new Date(health.computedAt).toLocaleString()}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

function DimensionCard({ name, dim, index }: { name: string; dim: IntegrationHealthDimension; index: number }) {
  const label = DIMENSION_LABELS[name] ?? dim.label ?? name
  const Icon = DIMENSION_ICONS[name] ?? Activity
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
      className="rounded-xl border border-border bg-card/60 p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10">
            <Icon className="h-3.5 w-3.5 text-primary" aria-hidden />
          </span>
          {label}
        </span>
        <span className="text-lg font-semibold tabular-nums text-foreground">{dim.score}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
        <motion.div
          className={cn("h-full rounded-full", barColor(dim.score))}
          initial={{ width: 0 }}
          animate={{ width: `${dim.score}%` }}
          transition={{ duration: 0.8, delay: index * 0.06 + 0.1, ease: "easeOut" }}
        />
      </div>
      <p className="mt-2 text-xs text-muted-foreground text-pretty">{dim.summary}</p>
    </motion.div>
  )
}

function HealthTrendChart({ snapshots }: { snapshots: IntegrationHealthSnapshot[] }) {
  const data = useMemo(() => {
    const ordered = [...snapshots].reverse()
    return ordered.map((s) => ({
      date: new Date(s.recordedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      score: s.score,
    }))
  }, [snapshots])

  const delta = data.length >= 2 ? data[data.length - 1].score - data[0].score : 0

  if (data.length < 2) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary">
          <TrendingUp className="h-5 w-5 text-muted-foreground" aria-hidden />
        </div>
        <p className="text-sm text-muted-foreground text-pretty">
          Record at least two snapshots to chart health trends for QBRs.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">{snapshots.length} snapshots</span>
        <span
          className={cn(
            "flex items-center gap-1 font-medium tabular-nums",
            delta >= 0 ? "text-success" : "text-destructive",
          )}
        >
          {delta >= 0 ? <TrendingUp className="h-3.5 w-3.5" aria-hidden /> : <TrendingDown className="h-3.5 w-3.5" aria-hidden />}
          {delta >= 0 ? "+" : ""}
          {delta} pts
        </span>
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="cs-health-gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <RechartsTooltip
              cursor={{ stroke: "var(--border)" }}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--popover-foreground)",
              }}
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke="var(--primary)"
              strokeWidth={2}
              fill="url(#cs-health-gradient)"
              animationDuration={900}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
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
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.25 }}
      className="flex gap-3 rounded-lg border border-border bg-card/50 p-4 transition-colors hover:border-primary/30"
    >
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
              <Link href={`/connectors?type=${suggestion.connectorType}`}>Open connectors</Link>
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
    </motion.div>
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
  const meta = SEVERITY_META[alert.severity]
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.25 }}
      className={cn("flex gap-3 rounded-lg border p-3", meta.ring)}
    >
      <span className="relative mt-1 flex h-2.5 w-2.5 shrink-0">
        <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", meta.dot)} />
        <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", meta.dot)} />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-foreground">{alert.title}</p>
          <Badge variant="outline" className={cn("capitalize", meta.text)}>
            {meta.label}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground text-pretty">{alert.message}</p>
        <div className="flex items-center gap-3 pt-0.5">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-muted-foreground" asChild>
            <Link href={`/workflows/${alert.workflowId}/builder`}>Open workflow</Link>
          </Button>
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
    </motion.div>
  )
}

export function CsDashboardTab() {
  const [busy, setBusy] = useState<string | null>(null)
  const [dismissingFailureId, setDismissingFailureId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const {
    data: health,
    error: healthError,
    isLoading: healthLoading,
    mutate: mutateHealth,
  } = useSWR("enterprise-integration-health", () => enterpriseApi.getIntegrationHealth(LOOKBACK_DAYS), {
    revalidateOnFocus: false,
  })

  const { data: history, error: historyError, mutate: mutateHistory } = useSWR(
    "enterprise-integration-health-history",
    () => enterpriseApi.getIntegrationHealthHistory(30),
    { revalidateOnFocus: false },
  )

  const { data: suggestionsData, error: suggestionsError, mutate: mutateSuggestions } = useSWR(
    "enterprise-integration-suggestions",
    () => enterpriseApi.getIntegrationSuggestions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  const { data: failureData, error: failuresError, mutate: mutateFailures } = useSWR(
    "workflow-failure-predictions",
    () => workflowsApi.listFailurePredictions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(null), 3000)
  }, [])

  const refreshAll = useCallback(async () => {
    setBusy("refresh")
    try {
      await Promise.all([mutateHealth(), mutateHistory(), mutateSuggestions(), mutateFailures()])
    } finally {
      setBusy(null)
    }
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

  const scanFailures = async () => {
    setBusy("failure-scan")
    try {
      const result = await workflowsApi.scanAllFailurePredictions()
      await mutateFailures()
      const suffix = result.errors.length > 0 ? ` (${result.errors.length} skipped)` : ""
      showToast(`Scanned ${result.scannedCount} workflows — ${result.alertCount} alerts${suffix}`)
    } catch {
      showToast("Failed to scan workflows")
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

  if (healthLoading && !health && !healthError) return <TabSkeleton rows={4} />

  const suggestions = suggestionsData?.suggestions ?? []
  const failures = failureData?.alerts ?? []
  const snapshots = history?.snapshots ?? []
  const dimensions = health?.dimensions ?? {}
  const risks = health?.risks ?? []
  const loadErrors = [
    healthError ? "Integration health" : null,
    historyError ? "Health history" : null,
    suggestionsError ? "Recommendations" : null,
    failuresError ? "Failure predictions" : null,
  ].filter(Boolean) as string[]

  const groupedFailures = SEVERITY_ORDER.map((sev) => ({
    severity: sev,
    items: failures.filter((f) => f.severity === sev),
  })).filter((g) => g.items.length > 0)

  return (
    <div className="space-y-6">
      <AnimatePresence>
        {toast ? (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
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
          </motion.div>
        ) : null}
      </AnimatePresence>

      {loadErrors.length > 0 ? (
        <div
          className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          role="alert"
        >
          <div className="space-y-1">
            <p className="flex items-center gap-2 text-sm font-medium text-foreground">
              <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden />
              Some CS data failed to load
            </p>
            <p className="text-sm text-muted-foreground text-pretty">
              {loadErrors.join(", ")} — check backend connectivity and run pending migrations.
            </p>
            {healthError ? (
              <p className="text-xs text-muted-foreground/80">{String(healthError.message || healthError)}</p>
            ) : null}
          </div>
          <Button variant="outline" size="sm" disabled={!!busy} onClick={() => void refreshAll()}>
            <RefreshCw className={cn("mr-1.5 h-4 w-4", busy === "refresh" && "animate-spin")} aria-hidden />
            Retry
          </Button>
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
            <Camera className={cn("mr-1.5 h-4 w-4", busy === "snapshot" && "animate-pulse")} aria-hidden />
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
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.entries(dimensions).map(([key, dim], i) => (
              <DimensionCard key={key} name={key} dim={dim} index={i} />
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
                <Badge variant={risk.severity === "high" ? "destructive" : "outline"}>{risk.score}/100</Badge>
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
            <CardDescription>Suggested connectors and workflows from audit usage patterns.</CardDescription>
          </div>
          <Button size="sm" disabled={!!busy} onClick={() => void scanSuggestions()}>
            <Sparkles className={cn("mr-1.5 h-4 w-4", busy === "scan" && "animate-pulse")} aria-hidden />
            Scan audit data
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {suggestions.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Lightbulb className="h-5 w-5 text-primary" aria-hidden />
              </div>
              <p className="text-sm font-medium text-foreground">No open recommendations</p>
              <p className="max-w-sm text-sm text-muted-foreground text-pretty">
                Run a scan after agents and operators use connectors to surface tailored next steps.
              </p>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {suggestions.map((s) => (
                <SuggestionCard
                  key={s.id}
                  suggestion={s}
                  onDismiss={(id) => void dismissSuggestion(id)}
                  dismissing={busy}
                />
              ))}
            </AnimatePresence>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div>
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-destructive" aria-hidden />
              <CardTitle className="text-base">Workflow failure predictions</CardTitle>
            </div>
            <CardDescription>Pre-failure alerts from auth expiry, rate limits, and missing scopes.</CardDescription>
          </div>
          <Button size="sm" disabled={!!busy} onClick={() => void scanFailures()}>
            <ShieldAlert className={cn("mr-1.5 h-4 w-4", busy === "failure-scan" && "animate-pulse")} aria-hidden />
            Scan workflows
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {failures.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-success/10">
                <ShieldCheck className="h-5 w-5 text-success" aria-hidden />
              </div>
              <p className="text-sm font-medium text-foreground">No open failure alerts</p>
              <p className="max-w-sm text-sm text-muted-foreground text-pretty">
                Scan all workflows to generate pre-failure predictions from connector auth, scopes, and run history.
              </p>
            </div>
          ) : (
            groupedFailures.map((group) => (
              <div key={group.severity} className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className={cn("h-1.5 w-1.5 rounded-full", SEVERITY_META[group.severity].dot)} aria-hidden />
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {SEVERITY_META[group.severity].label}
                  </span>
                  <span className="text-xs tabular-nums text-muted-foreground/70">{group.items.length}</span>
                </div>
                <AnimatePresence initial={false}>
                  {group.items.map((alert) => (
                    <FailureAlertRow
                      key={alert.id}
                      alert={alert}
                      onDismiss={(id) => void dismissFailure(id)}
                      dismissing={dismissingFailureId}
                    />
                  ))}
                </AnimatePresence>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
