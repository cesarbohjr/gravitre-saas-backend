"use client"

/**
 * Failure alerts panel — shared by Activity hub tab and legacy redirect page.
 */

import { useMemo, useState } from "react"
import useSWR from "swr"
import { AnimatePresence } from "framer-motion"
import { toast } from "sonner"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { AlertTriangle, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react"

type StatusFilter = "open" | "dismissed" | "all"

export function FailureAlertsPanel() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open")
  const [dismissingId, setDismissingId] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)

  const statusParam = statusFilter === "all" ? undefined : statusFilter

  const { data, error, isLoading, mutate } = useSWR(
    ["workflow-failure-predictions", statusParam ?? "all"],
    () => workflowsApi.listFailurePredictions({ status: statusParam }),
    { revalidateOnFocus: false },
  )

  const alerts = data?.alerts ?? []
  const grouped = useMemo(() => groupFailureAlertsBySeverity(alerts), [alerts])

  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 }
    for (const alert of alerts) {
      counts[alert.severity] += 1
    }
    return counts
  }, [alerts])

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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" disabled={scanning} onClick={() => void scanAll()}>
          <ShieldAlert className={cn("mr-1.5 h-4 w-4", scanning && "animate-pulse")} aria-hidden />
          Scan all workflows
        </Button>
        <Button variant="outline" size="sm" disabled={isLoading} onClick={() => void mutate()}>
          <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden />
          Refresh
        </Button>
      </div>

      <OutcomeOpsPanel />

      <div className="flex flex-wrap items-center gap-3">
        <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
          <SelectTrigger className="w-[160px]" aria-label="Filter by status">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="open">Open alerts</SelectItem>
            <SelectItem value="dismissed">Dismissed</SelectItem>
            <SelectItem value="all">All statuses</SelectItem>
          </SelectContent>
        </Select>
        {!isLoading && !error ? (
          <Badge variant="outline" className="tabular-nums">
            {alerts.length} alert{alerts.length === 1 ? "" : "s"}
          </Badge>
        ) : null}
      </div>

      {!isLoading && !error && alerts.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {(Object.keys(severityCounts) as Array<keyof typeof severityCounts>).map((severity) =>
            severityCounts[severity] > 0 ? (
              <Badge
                key={severity}
                variant="outline"
                className={cn("capitalize", FAILURE_SEVERITY_META[severity].text)}
              >
                {FAILURE_SEVERITY_META[severity].label}: {severityCounts[severity]}
              </Badge>
            ) : null,
          )}
        </div>
      ) : null}

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
        <div className="space-y-6">
          {grouped.map((group) => (
            <Card key={group.severity}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <span
                    className={cn("h-2 w-2 rounded-full", FAILURE_SEVERITY_META[group.severity].dot)}
                    aria-hidden
                  />
                  <CardTitle className="text-base">{FAILURE_SEVERITY_META[group.severity].label}</CardTitle>
                  <Badge variant="outline" className="tabular-nums">
                    {group.items.length}
                  </Badge>
                </div>
                <CardDescription>
                  {group.severity === "critical" || group.severity === "high"
                    ? "Address these before the next scheduled run."
                    : "Review when planning workflow changes."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
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
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
        <p className="text-pretty">
          Predictions are advisory. Dismiss alerts after remediation or when risk is accepted.
        </p>
      </div>
    </div>
  )
}
