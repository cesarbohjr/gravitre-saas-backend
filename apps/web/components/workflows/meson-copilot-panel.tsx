"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Lightbulb,
  Loader2,
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
import { GlowOrb, StatusBeacon, ShimmerText } from "@/components/gravitre/premium-effects"
import { useMotionPrefs } from "@/lib/animations"
import {
  mesonApi,
  type MesonAlert,
  type MesonEditProposalResponse,
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

function severityBeacon(severity: string): "warning" | "error" | "idle" {
  if (severity === "critical") return "error"
  if (severity === "warning") return "warning"
  return "idle"
}

export function MesonCopilotPanel({
  open,
  onClose,
  workflowId,
  canPersist,
  nodes,
  edges,
  onAcceptSuggestion,
  onDismissSuggestion,
  onApplyInsight,
  onFixAlert,
  onEditApplied,
  crossWorkflowSignals,
}: {
  open: boolean
  onClose: () => void
  workflowId?: string
  canPersist?: boolean
  nodes: Array<{
    id?: string
    type: string
    name: string
    vendor?: string
    selectedAction?: string
    description?: string
    position?: { x: number; y: number }
  }>
  edges?: Array<{ id?: string; from: string; to: string }>
  onAcceptSuggestion: (suggestion: MesonSuggestion) => void
  onDismissSuggestion: (suggestionId: string) => void
  onApplyInsight?: (insight: MesonInsight) => void
  onFixAlert?: (alert: MesonAlert) => void
  onEditApplied?: () => void | Promise<void>
  crossWorkflowSignals?: Array<{ message: string; count?: number }>
}) {
  const { reduced, container, item } = useMotionPrefs()
  const [suggestions, setSuggestions] = useState<MesonSuggestion[]>([])
  const [alerts, setAlerts] = useState<MesonAlert[]>([])
  const [insights, setInsights] = useState<MesonInsight[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [loadingInsights, setLoadingInsights] = useState(false)
  const [fixingAlertId, setFixingAlertId] = useState<string | null>(null)
  const [fixedAlertId, setFixedAlertId] = useState<string | null>(null)
  const [appliedInsightId, setAppliedInsightId] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<string[]>(() => loadDismissed(workflowId))
  const [editInstruction, setEditInstruction] = useState("")
  const [editLoading, setEditLoading] = useState(false)
  const [applyLoading, setApplyLoading] = useState(false)
  const [editProposal, setEditProposal] = useState<MesonEditProposalResponse | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<string | null>(null)
  const [explainLoading, setExplainLoading] = useState(false)

  useEffect(() => {
    // Sync dismissed list from localStorage when switching workflows.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDismissed(loadDismissed(workflowId))
    setEditProposal(null)
    setEditError(null)
    setExplanation(null)
  }, [workflowId])

  const lastNode = nodes.length > 0 ? nodes[nodes.length - 1] : null

  useEffect(() => {
    if (!open) return
    let cancelled = false
    // Kick off async data fetch + loading flags (external sync).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingAlerts(true)
    setLoadingInsights(true)
    void mesonApi
      .alerts()
      .then((res) => {
        if (!cancelled) {
          const dismissedIds = new Set(loadDismissed(workflowId))
          setAlerts((res.alerts ?? []).filter((alert) => !dismissedIds.has(alert.id)))
        }
      })
      .catch(() => {
        if (!cancelled) setAlerts([])
      })
      .finally(() => {
        if (!cancelled) setLoadingAlerts(false)
      })
    const insightsRequest =
      canPersist && workflowId
        ? mesonApi.optimizations(workflowId)
        : mesonApi.insights()
    void insightsRequest
      .then((res) => {
        if (!cancelled) {
          const dismissedIds = new Set(loadDismissed(workflowId))
          setInsights(
            (res.insights ?? [])
              .filter((insight) => !dismissedIds.has(insight.id))
              .slice(0, 2),
          )
        }
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
  }, [open, workflowId, canPersist])

  useEffect(() => {
    if (!open || nodes.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
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

  const handleAccept = useCallback(
    (suggestion: MesonSuggestion) => {
      // Optimistically collapse the card out (suggestions refetch on node change).
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id))
      onAcceptSuggestion(suggestion)
    },
    [onAcceptSuggestion],
  )

  const handleFixAlert = useCallback(
    (alert: MesonAlert) => {
      if (!onFixAlert) return
      setFixingAlertId(alert.id)
      try {
        onFixAlert(alert)
        const next = [...dismissed, alert.id]
        setDismissed(next)
        saveDismissed(workflowId, next)
        // brief success checkmark before the row clears
        setFixedAlertId(alert.id)
        window.setTimeout(() => {
          setAlerts((prev) => prev.filter((item) => item.id !== alert.id))
          setFixedAlertId(null)
        }, 600)
      } finally {
        setFixingAlertId(null)
      }
    },
    [dismissed, onFixAlert, workflowId],
  )

  const handleApplyInsight = useCallback(
    (insight: MesonInsight) => {
      if (!onApplyInsight) return
      setAppliedInsightId(insight.id)
      onApplyInsight(insight)
      const next = [...dismissed, insight.id]
      setDismissed(next)
      saveDismissed(workflowId, next)
      window.setTimeout(() => {
        setInsights((prev) => prev.filter((item) => item.id !== insight.id))
        setAppliedInsightId(null)
      }, 600)
    },
    [dismissed, onApplyInsight, workflowId],
  )

  const visibleAlerts = useMemo(() => alerts.slice(0, 5), [alerts])

  const handleProposeEdit = useCallback(async () => {
    if (!workflowId || !canPersist || !editInstruction.trim()) return
    setEditLoading(true)
    setEditError(null)
    try {
      const proposal = await mesonApi.edit({
        workflowId,
        instruction: editInstruction.trim(),
        workflowState: {
          nodes: nodes.map((n) => ({
            id: n.id,
            type: n.type,
            name: n.name,
            vendor: n.vendor,
            selectedAction: n.selectedAction,
            description: n.description,
            position: n.position,
          })),
          edges: (edges ?? []).map((e) => ({
            id: e.id,
            from_node_id: e.from,
            to_node_id: e.to,
          })),
        },
      })
      setEditProposal(proposal)
    } catch (err) {
      setEditProposal(null)
      setEditError(err instanceof Error ? err.message : "Edit proposal failed")
    } finally {
      setEditLoading(false)
    }
  }, [workflowId, canPersist, editInstruction, nodes, edges])

  const handleApplyEdit = useCallback(async () => {
    if (!workflowId || !editProposal?.proposalId) return
    setApplyLoading(true)
    setEditError(null)
    try {
      await mesonApi.applyEdit({
        workflowId,
        proposalId: editProposal.proposalId,
      })
      setEditProposal(null)
      setEditInstruction("")
      await onEditApplied?.()
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Apply failed")
    } finally {
      setApplyLoading(false)
    }
  }, [workflowId, editProposal, onEditApplied])

  const handleExplain = useCallback(async () => {
    if (!workflowId || !canPersist) return
    setExplainLoading(true)
    try {
      const res = await mesonApi.explain(workflowId)
      setExplanation(res.explanation || null)
    } catch {
      setExplanation("Could not explain this workflow right now.")
    } finally {
      setExplainLoading(false)
    }
  }, [workflowId, canPersist])

  // Bounce the alert badge when the count increases.
  const [badgeBounce, setBadgeBounce] = useState(0)
  const prevAlertCount = useRef(0)
  useEffect(() => {
    if (visibleAlerts.length > prevAlertCount.current) {
      setBadgeBounce((n) => n + 1)
    }
    prevAlertCount.current = visibleAlerts.length
  }, [visibleAlerts.length])

  if (!open) return null

  return (
    <motion.aside
      initial={reduced ? { opacity: 0 } : { x: 36, opacity: 0 }}
      animate={reduced ? { opacity: 1 } : { x: 0, opacity: 1 }}
      transition={reduced ? { duration: 0.12 } : { type: "spring", stiffness: 360, damping: 34 }}
      className={cn(
        "relative w-[280px] shrink-0 border-l border-border bg-card flex flex-col overflow-hidden",
      )}
      aria-label="Meson AI Copilot"
    >
      {/* soft attention glow behind the header */}
      {!reduced ? (
        <GlowOrb
          size={160}
          color="violet"
          animate
          className="pointer-events-none absolute -right-10 -top-10 opacity-40"
        />
      ) : null}

      <div className="relative flex items-center justify-between border-b border-border px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Meson</span>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} aria-label="Close Meson panel">
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="relative flex-1 overflow-y-auto">
        {/* Conversational edit (Phase 2) */}
        {canPersist && workflowId ? (
          <section className="border-b border-border p-3">
            <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Edit with Meson
            </h3>
            <textarea
              value={editInstruction}
              onChange={(e) => setEditInstruction(e.target.value)}
              placeholder='e.g. "add a HubSpot check before sending"'
              className="mb-2 min-h-[64px] w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              aria-label="Natural language canvas edit"
            />
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                className="h-7 flex-1 gap-1 text-[10px]"
                disabled={editLoading || !editInstruction.trim()}
                onClick={() => void handleProposeEdit()}
              >
                {editLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                Propose diff
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1 px-2 text-[10px]"
                disabled={explainLoading}
                onClick={() => void handleExplain()}
              >
                {explainLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                Explain
              </Button>
            </div>
            {editError ? (
              <p className="mt-2 text-[10px] text-destructive">{editError}</p>
            ) : null}
            {explanation ? (
              <p className="mt-2 rounded-md border border-border bg-secondary/30 p-2 text-[10px] text-muted-foreground">
                {explanation}
              </p>
            ) : null}
            {editProposal ? (
              <div className="mt-2 space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5">
                <p className="text-xs font-medium text-foreground">{editProposal.summary}</p>
                {editProposal.diff?.available && editProposal.diff.prior ? (
                  <pre className="max-h-32 overflow-auto rounded bg-muted/40 p-2 text-[9px] leading-snug">
                    {JSON.stringify(
                      {
                        summary: editProposal.diff.summary,
                        added: editProposal.diff.added_nodes,
                        removed: editProposal.diff.removed_nodes,
                        changed: editProposal.diff.changed_nodes,
                      },
                      null,
                      2,
                    )}
                  </pre>
                ) : (
                  <p className="text-[10px] text-muted-foreground">
                    {editProposal.diff?.note || "No structural changes proposed."}
                  </p>
                )}
                {editProposal.confidence != null ? (
                  <p className="text-[9px] text-muted-foreground">
                    {editProposal.confidenceIsEstimate !== false
                      ? "Estimated confidence"
                      : "Confidence"}{" "}
                    {Math.round(editProposal.confidence * 100)}%
                    {editProposal.confidenceSource
                      ? ` · ${editProposal.confidenceSource}`
                      : ""}
                  </p>
                ) : null}
                <div className="flex justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => setEditProposal(null)}
                  >
                    Discard
                  </Button>
                  <Button
                    size="sm"
                    className="h-6 gap-1 px-2 text-[10px]"
                    disabled={applyLoading || !editProposal.diff?.available}
                    onClick={() => void handleApplyEdit()}
                  >
                    {applyLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3 w-3" />}
                    Apply edit
                  </Button>
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {crossWorkflowSignals && crossWorkflowSignals.length > 0 ? (
          <section className="border-b border-border p-3">
            <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Cross-workflow
            </h3>
            <div className="space-y-1.5">
              {crossWorkflowSignals.slice(0, 3).map((signal, idx) => (
                <p
                  key={`${signal.message}-${idx}`}
                  className="rounded border border-orange-500/25 bg-orange-500/5 px-2 py-1.5 text-[10px] text-orange-700 dark:text-orange-400"
                >
                  {signal.message}
                </p>
              ))}
            </div>
          </section>
        ) : null}

        {/* Suggestions */}
        <section className="border-b border-border p-3">
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Meson suggests
          </h3>
          {loadingSuggestions ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : suggestions.length === 0 ? (
            <p className="text-xs text-muted-foreground">Add nodes to get step suggestions.</p>
          ) : (
            <motion.div className="space-y-2" variants={container} initial="initial" animate="animate">
              <AnimatePresence initial={false}>
                {suggestions.map((suggestion) => {
                  const conf = suggestion.confidence ?? null
                  const strong = conf != null && conf >= 0.75
                  return (
                    <motion.div
                      key={suggestion.id}
                      layout={!reduced}
                      variants={item}
                      exit={
                        reduced
                          ? { opacity: 0 }
                          : { opacity: 0, height: 0, marginBottom: 0, scale: 0.96 }
                      }
                      className={cn(
                        "overflow-hidden rounded-lg border p-2.5",
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
                      {conf != null ? (
                        <div className="mt-2">
                          <div className="flex items-center justify-between text-[9px] text-muted-foreground">
                            <span>
                              {suggestion.confidenceIsEstimate !== false
                                ? "Estimated confidence"
                                : "Confidence"}
                            </span>
                            <span className="tabular-nums">{Math.round(conf * 100)}%</span>
                          </div>
                          <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                            <motion.div
                              className={cn(
                                "h-full rounded-full",
                                strong ? "bg-emerald-500" : "bg-amber-500",
                              )}
                              initial={{ width: reduced ? `${conf * 100}%` : 0 }}
                              animate={{ width: `${conf * 100}%` }}
                              transition={reduced ? { duration: 0 } : { duration: 0.6, ease: "easeOut" }}
                            />
                          </div>
                        </div>
                      ) : null}
                      <div className="mt-2 flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-[10px]"
                          onClick={() => handleDismiss(suggestion.id)}
                          aria-label="Dismiss suggestion"
                        >
                          <X className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          className="h-6 gap-1 px-2 text-[10px]"
                          onClick={() => handleAccept(suggestion)}
                        >
                          <Plus className="h-3 w-3" />
                          Add
                        </Button>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </motion.div>
          )}
        </section>

        {/* Alerts */}
        <section className="border-b border-border p-3">
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Alerts</h3>
            {visibleAlerts.length > 0 ? (
              <motion.span
                key={badgeBounce}
                initial={reduced ? false : { scale: 0.6 }}
                animate={reduced ? {} : { scale: [0.6, 1.25, 1] }}
                transition={{ duration: 0.35, ease: "easeOut" }}
              >
                <Badge variant="secondary" className="h-4 px-1.5 text-[10px] tabular-nums">
                  {visibleAlerts.length}
                </Badge>
              </motion.span>
            ) : null}
          </div>
          {loadingAlerts ? (
            <Skeleton className="h-12 w-full" />
          ) : visibleAlerts.length === 0 ? (
            <motion.div
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.9 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, scale: 1 }}
              transition={reduced ? { duration: 0.12 } : { type: "spring", stiffness: 380, damping: 24 }}
              className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-2"
            >
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              <span className="text-xs text-muted-foreground">No issues detected</span>
            </motion.div>
          ) : (
            <motion.div className="space-y-2" variants={container} initial="initial" animate="animate">
              <AnimatePresence initial={false}>
                {visibleAlerts.map((alert) => {
                  const Icon = severityIcon(alert.severity)
                  const beacon = severityBeacon(alert.severity)
                  const isFixed = fixedAlertId === alert.id
                  return (
                    <motion.div
                      key={alert.id}
                      layout={!reduced}
                      variants={item}
                      exit={reduced ? { opacity: 0 } : { opacity: 0, height: 0, marginBottom: 0 }}
                      className="overflow-hidden rounded-lg border border-border bg-secondary/30 p-2.5"
                    >
                      <div className="flex items-start gap-2">
                        {beacon !== "idle" ? (
                          <span className="mt-0.5">
                            <StatusBeacon status={beacon} size="sm" />
                          </span>
                        ) : (
                          <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        )}
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
                          disabled={fixingAlertId === alert.id || isFixed}
                          onClick={() => handleFixAlert(alert)}
                        >
                          {isFixed ? (
                            <>
                              <CheckCircle className="h-3 w-3 text-emerald-500" />
                              Fixed
                            </>
                          ) : fixingAlertId === alert.id ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              Fixing
                            </>
                          ) : (
                            <>
                              <Wrench className="h-3 w-3" />
                              {alert.fixLabel ?? "Fix"}
                            </>
                          )}
                        </Button>
                      ) : null}
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </motion.div>
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
            <motion.div className="space-y-2" variants={container} initial="initial" animate="animate">
              {insights.map((insight) => {
                const applied = appliedInsightId === insight.id
                return (
                  <motion.div
                    key={insight.id}
                    variants={item}
                    className="rounded-lg border border-border bg-secondary/20 p-2.5"
                  >
                    <div className="flex items-start gap-2">
                      <TrendingUp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
                      <div className="min-w-0 flex-1">
                        {applied && !reduced ? (
                          <ShimmerText className="text-xs font-medium text-foreground">
                            {insight.title}
                          </ShimmerText>
                        ) : (
                          <p className="text-xs font-medium text-foreground">{insight.title}</p>
                        )}
                        <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">{insight.summary}</p>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2 h-6 gap-1 px-2 text-[10px]"
                      onClick={() => handleApplyInsight(insight)}
                      disabled={!onApplyInsight}
                    >
                      Apply
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </motion.div>
                )
              })}
            </motion.div>
          )}
        </section>
      </div>
    </motion.aside>
  )
}
