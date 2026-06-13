"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Lightbulb,
  Plus,
  Sparkles,
  TrendingUp,
  Wrench,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  mesonApi,
  type MesonAlert,
  type MesonInsight,
  type MesonSuggestion,
} from "@/lib/api"

const DISMISSED_KEY_PREFIX = "gravitre:meson-dismissed:"

function loadDismissed(workflowId?: string): string[] {
  if (typeof window === "undefined" || !workflowId) return []
  try {
    const raw = localStorage.getItem(`${DISMISSED_KEY_PREFIX}${workflowId}`)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveDismissed(workflowId: string | undefined, ids: string[]) {
  if (typeof window === "undefined" || !workflowId) return
  localStorage.setItem(`${DISMISSED_KEY_PREFIX}${workflowId}`, JSON.stringify(ids))
}

function confidenceClass(confidence?: number) {
  if (confidence == null) return "border-border"
  if (confidence >= 0.75) return "border-emerald-500/40 bg-emerald-500/5"
  return "border-amber-500/40 bg-amber-500/5"
}

function severityIcon(severity: string) {
  if (severity === "critical") return AlertTriangle
  if (severity === "warning") return AlertTriangle
  return CheckCircle
}

export function MesonCopilotPanel({
  open,
  onClose,
  workflowId,
  canPersist,
  nodes,
  onAcceptSuggestion,
  onDismissSuggestion,
  onApplyInsight,
  onFixAlert,
}: {
  open: boolean
  onClose: () => void
  workflowId?: string
  canPersist?: boolean
  nodes: Array<{ type: string; name: string; vendor?: string }>
  onAcceptSuggestion: (suggestion: MesonSuggestion) => void
  onDismissSuggestion: (suggestionId: string) => void
  onApplyInsight?: (insight: MesonInsight) => void
  onFixAlert?: (alert: MesonAlert) => void
}) {
  const [suggestions, setSuggestions] = useState<MesonSuggestion[]>([])
  const [alerts, setAlerts] = useState<MesonAlert[]>([])
  const [insights, setInsights] = useState<MesonInsight[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [loadingInsights, setLoadingInsights] = useState(false)
  const [fixingAlertId, setFixingAlertId] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<string[]>(() => loadDismissed(workflowId))

  useEffect(() => {
    setDismissed(loadDismissed(workflowId))
  }, [workflowId])

  const lastNode = nodes.length > 0 ? nodes[nodes.length - 1] : null

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoadingAlerts(true)
    setLoadingInsights(true)
    void mesonApi
      .alerts()
      .then((res) => {
        if (!cancelled) setAlerts(res.alerts ?? [])
      })
      .catch(() => {
        if (!cancelled) setAlerts([])
      })
      .finally(() => {
        if (!cancelled) setLoadingAlerts(false)
      })
    void mesonApi
      .insights()
      .then((res) => {
        if (!cancelled) setInsights((res.insights ?? []).slice(0, 2))
      })
      .catch(() => {
        if (!cancelled) setInsights([])
      })
      .finally(() => {
        if (!cancelled) setLoadingInsights(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, workflowId])

  useEffect(() => {
    if (!open || nodes.length === 0) {
      setSuggestions([])
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      setLoadingSuggestions(true)
      void mesonApi
        .suggestions({
          workflowState: {
            nodes: nodes.map((n) => ({ type: n.type, name: n.name, vendor: n.vendor })),
          },
          lastAddedNode: lastNode
            ? { type: lastNode.type, name: lastNode.name, vendor: lastNode.vendor }
            : undefined,
          workflowId: canPersist ? workflowId : undefined,
        })
        .then((res) => {
          if (cancelled) return
          setSuggestions(
            (res.suggestions ?? []).filter((s) => !dismissed.includes(s.id)).slice(0, 3),
          )
        })
        .catch(() => {
          if (!cancelled) setSuggestions([])
        })
        .finally(() => {
          if (!cancelled) setLoadingSuggestions(false)
        })
    }, 400)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [open, nodes, dismissed, canPersist, workflowId, lastNode])

  const handleDismiss = useCallback(
    (suggestionId: string) => {
      const next = [...dismissed, suggestionId]
      setDismissed(next)
      saveDismissed(workflowId, next)
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestionId))
      onDismissSuggestion(suggestionId)
    },
    [dismissed, onDismissSuggestion, workflowId],
  )

  const handleFixAlert = useCallback(
    (alert: MesonAlert) => {
      if (!onFixAlert) return
      setFixingAlertId(alert.id)
      try {
        onFixAlert(alert)
        setAlerts((prev) => prev.filter((item) => item.id !== alert.id))
      } finally {
        setFixingAlertId(null)
      }
    },
    [onFixAlert],
  )

  const visibleAlerts = useMemo(() => alerts.slice(0, 5), [alerts])

  if (!open) return null

  return (
    <aside
      className={cn(
        "w-[280px] shrink-0 border-l border-border bg-card flex flex-col overflow-hidden",
        "animate-in slide-in-from-right-2 duration-200",
      )}
      aria-label="Meson AI Copilot"
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Meson</span>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} aria-label="Close Meson panel">
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Suggestions */}
        <section className="border-b border-border p-3">
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Meson suggests
          </h3>
          {loadingSuggestions ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : suggestions.length === 0 ? (
            <p className="text-xs text-muted-foreground">Add nodes to get step suggestions.</p>
          ) : (
            <div className="space-y-2">
              {suggestions.map((suggestion) => (
                <div
                  key={suggestion.id}
                  className={cn(
                    "rounded-lg border p-2.5",
                    confidenceClass(suggestion.confidence),
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-info/10 text-info">
                      <Lightbulb className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-foreground">{suggestion.label}</p>
                      {suggestion.reason ? (
                        <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">
                          {suggestion.reason}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-2 flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[10px]"
                      onClick={() => handleDismiss(suggestion.id)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                    <Button
                      size="sm"
                      className="h-6 gap-1 px-2 text-[10px]"
                      onClick={() => onAcceptSuggestion(suggestion)}
                    >
                      <Plus className="h-3 w-3" />
                      Add
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Alerts */}
        <section className="border-b border-border p-3">
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Alerts</h3>
            {visibleAlerts.length > 0 ? (
              <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
                {visibleAlerts.length}
              </Badge>
            ) : null}
          </div>
          {loadingAlerts ? (
            <Skeleton className="h-12 w-full" />
          ) : visibleAlerts.length === 0 ? (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-2">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              <span className="text-xs text-muted-foreground">No issues detected</span>
            </div>
          ) : (
            <div className="space-y-2">
              {visibleAlerts.map((alert) => {
                const Icon = severityIcon(alert.severity)
                return (
                  <div key={alert.id} className="rounded-lg border border-border bg-secondary/30 p-2.5">
                    <div className="flex items-start gap-2">
                      <Icon
                        className={cn(
                          "mt-0.5 h-3.5 w-3.5 shrink-0",
                          alert.severity === "critical"
                            ? "text-destructive"
                            : alert.severity === "warning"
                              ? "text-warning"
                              : "text-muted-foreground",
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-foreground">{alert.title}</p>
                        <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">{alert.message}</p>
                      </div>
                    </div>
                    {(alert.autoFixable || alert.actionTarget) && onFixAlert ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2 h-6 gap-1 px-2 text-[10px]"
                        disabled={fixingAlertId === alert.id}
                        onClick={() => handleFixAlert(alert)}
                      >
                        <Wrench className="h-3 w-3" />
                        {alert.fixLabel ?? "Fix"}
                      </Button>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </section>

        {/* Optimizations */}
        <section className="p-3">
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Optimize</h3>
          {loadingInsights ? (
            <Skeleton className="h-14 w-full" />
          ) : insights.length === 0 ? (
            <p className="text-xs text-muted-foreground">No optimization tips yet.</p>
          ) : (
            <div className="space-y-2">
              {insights.map((insight) => (
                <div key={insight.id} className="rounded-lg border border-border bg-secondary/20 p-2.5">
                  <div className="flex items-start gap-2">
                    <TrendingUp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-foreground">{insight.title}</p>
                      <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">{insight.summary}</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2 h-6 gap-1 px-2 text-[10px]"
                    onClick={() => onApplyInsight?.(insight)}
                    disabled={!onApplyInsight}
                  >
                    Apply
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </aside>
  )
}
