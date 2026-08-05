"use client"

/**
 * Failure alerts panel — shared by Activity hub tab and legacy redirect page.
 *
 * Layout mirrors the Activity inspector: one toolbar row, then a single internal
 * scroll region. Severity groups collapse so a long tail of low-severity alerts
 * can't push the actionable ones off-screen.
 */

import { useMemo, useState } from "react"
import useSWR from "swr"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { toast } from "sonner"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  FailureAlertRow,
  FAILURE_SEVERITY_META,
  groupFailureAlertsBySeverity,
} from "@/components/workflows/failure-prediction-alerts"
import { OutcomeOpsPanel } from "@/components/workflows/outcome-ops-panel"
import { workflowsApi } from "@/lib/api"
import { cn } from "@/lib/utils"
import { AlertTriangle, ChevronDown, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react"

type StatusFilter = "open" | "dismissed" | "all"
type Severity = "critical" | "high" | "medium" | "low"

export function FailureAlertsPanel() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open")
  const [dismissingId, setDismissingId] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [severityFilter, setSeverityFilter] = useState<Severity | null>(null)
  const [opsOpen, setOpsOpen] = useState(false)
  const reduceMotion = useReducedMotion()

  const statusParam = statusFilter === "all" ? undefined : statusFilter

  const { data, error, isLoading, mutate } = useSWR(
    ["workflow-failure-predictions", statusParam ?? "all"],
    () => workflowsApi.listFailurePredictions({ status: statusParam }),
    { revalidateOnFocus: false },
  )

  const alerts = data?.alerts ?? []

  // Severity counts come from the unfiltered set so the chips keep showing what
  // exists while one of them is narrowing the list.
  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 }
    for (const alert of alerts) {
      counts[alert.severity] += 1
    }
    return counts
  }, [alerts])

  const visibleAlerts = useMemo(
    () => (severityFilter ? alerts.filter((alert) => alert.severity === severityFilter) : alerts),
    [alerts, severityFilter],
  )

  const grouped = useMemo(() => groupFailureAlertsBySeverity(visibleAlerts), [visibleAlerts])

  const scanAll = async () => {
    setScanning(true)
    try {
      const result = await workflowsApi.scanAllFailurePredictions()
      await mutate()
      toast.success(
        `Scanned ${result.scannedCount} workflow${result.scannedCount === 1 ? "" : "s"} — ${result.alertCount} alert${result.alertCount === 1 ? "" : "s"}`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Scan failed")
    } finally {
      setScanning(false)
    }
  }

  const dismiss = async (id: string) => {
    setDismissingId(id)
    try {
      await workflowsApi.dismissFailurePrediction(id)
      await mutate()
      toast.success("Alert dismissed")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Dismiss failed")
    } finally {
      setDismissingId(null)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {/* One toolbar row — this was previously three stacked rows (actions,
          status select + total, severity badges) before any alert was visible. */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
          <SelectTrigger className="h-8 w-[150px]" aria-label="Filter by status">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="open">Open alerts</SelectItem>
            <SelectItem value="dismissed">Dismissed</SelectItem>
            <SelectItem value="all">All statuses</SelectItem>
          </SelectContent>
        </Select>

        {/* Severity counts were decorative badges; as chips they narrow the list,
            which is what anyone reading them actually wants to do next. */}
        {!isLoading && !error && alerts.length > 0 ? (
          <motion.div layout={!reduceMotion} className="flex flex-wrap items-center gap-1.5">
            {(Object.keys(severityCounts) as Severity[]).map((severity) =>
              severityCounts[severity] > 0 ? (
                <button
                  key={severity}
                  type="button"
                  aria-pressed={severityFilter === severity}
                  onClick={() =>
                    setSeverityFilter((current) => (current === severity ? null : severity))
                  }
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    severityFilter === severity
                      ? cn("border-transparent", FAILURE_SEVERITY_META[severity].ring)
                      : "border-border text-muted-foreground hover:bg-muted/60",
                  )}
                >
                  <span
                    className={cn("h-1.5 w-1.5 rounded-full", FAILURE_SEVERITY_META[severity].dot)}
                    aria-hidden
                  />
                  <span className={severityFilter === severity ? FAILURE_SEVERITY_META[severity].text : undefined}>
                    {FAILURE_SEVERITY_META[severity].label}
                  </span>
                  <span className="tabular-nums">{severityCounts[severity]}</span>
                </button>
              ) : null,
            )}
            {severityFilter ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground"
                onClick={() => setSeverityFilter(null)}
              >
                Clear
              </Button>
            ) : null}
          </motion.div>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {/* Demoted from a full-width footer card to a caption — the sentence is
              still available on hover/focus for anyone who needs it. */}
          <span
            className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex"
            title="Predictions are advisory. Dismiss alerts after remediation or when risk is accepted."
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden />
            Predictions are advisory
          </span>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            disabled={scanning}
            onClick={() => void scanAll()}
          >
            <ShieldAlert className={cn("mr-1.5 h-4 w-4", scanning && "animate-pulse")} aria-hidden />
            Scan all
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            disabled={isLoading}
            onClick={() => void mutate()}
          >
            <RefreshCw className={cn("mr-1.5 h-4 w-4", isLoading && "animate-spin")} aria-hidden />
            Refresh
          </Button>
        </div>
      </div>

      {/* Everything below scrolls as one region so the toolbar stays put. */}
      <div className="min-h-0 flex-1 space-y-3 lg:overflow-y-auto">
        {/* Ops summary is context, not the task — collapsed by default so alerts
            are the first thing on screen. */}
        <Collapsible open={opsOpen} onOpenChange={setOpsOpen}>
          <CollapsibleTrigger className="group flex w-full items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <ChevronDown
              className={cn("h-3.5 w-3.5 transition-transform duration-200", !opsOpen && "-rotate-90")}
              aria-hidden
            />
            Ops summary
          </CollapsibleTrigger>
          <CollapsibleContent className="overflow-hidden pt-3 data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            <OutcomeOpsPanel />
          </CollapsibleContent>
        </Collapsible>

        {error ? (
          <WorkSectionErrorCard
            title="Failed to load failure predictions"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={() => void mutate()}
          />
        ) : isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-lg" />
            ))}
          </div>
        ) : alerts.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <ShieldCheck className="h-6 w-6 text-success" aria-hidden />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  {statusFilter === "open" ? "No open failure alerts" : "No alerts for this filter"}
                </p>
                <p className="max-w-md text-sm text-muted-foreground text-pretty">
                  Scan all workflows to generate pre-failure predictions from connector health and recent
                  runs.
                </p>
              </div>
              <Button size="sm" disabled={scanning} onClick={() => void scanAll()}>
                <ShieldAlert className="mr-1.5 h-4 w-4" aria-hidden />
                Scan workflows
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {grouped.map((group) => (
              <SeverityGroup
                key={group.severity}
                severity={group.severity}
                count={group.items.length}
              >
                <AnimatePresence initial={false}>
                  {group.items.map((alert) => (
                    <FailureAlertRow
                      key={alert.id}
                      alert={alert}
                      onDismiss={(id) => void dismiss(id)}
                      dismissing={dismissingId}
                    />
                  ))}
                </AnimatePresence>
              </SeverityGroup>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Critical and high stay open — those are the ones the toolbar copy tells you to
 * address before the next run. Medium and low collapse behind their count.
 */
function SeverityGroup({
  severity,
  count,
  children,
}: {
  severity: Severity
  count: number
  children: React.ReactNode
}) {
  const meta = FAILURE_SEVERITY_META[severity]
  const [open, setOpen] = useState(severity === "critical" || severity === "high")

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-lg border border-border bg-card"
    >
      <CollapsibleTrigger className="group flex w-full items-center gap-2 px-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
            !open && "-rotate-90",
          )}
          aria-hidden
        />
        <span className={cn("h-2 w-2 shrink-0 rounded-full", meta.dot)} aria-hidden />
        <span className="text-sm font-medium text-foreground">{meta.label}</span>
        <Badge variant="outline" className="tabular-nums">
          {count}
        </Badge>
        <span className="ml-auto hidden truncate text-xs text-muted-foreground sm:block">
          {severity === "critical" || severity === "high"
            ? "Address before the next scheduled run."
            : "Review when planning workflow changes."}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
        <div className="space-y-2 px-3 pb-3">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}
