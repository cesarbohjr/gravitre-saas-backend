"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { ScrollText, Download, Lock, CheckCircle2, AlertTriangle, Clock } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseTransparencyLogsResponse } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  pending_approval: "bg-amber-500/15 text-amber-600",
  in_progress: "bg-primary/15 text-primary",
  blocked: "bg-muted text-muted-foreground",
  cancelled: "bg-muted text-muted-foreground",
}

export function TransparencyTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<EnterpriseTransparencyLogsResponse>(
    "enterprise-transparency-logs",
    () => enterpriseApi.getTransparencyLogs({ limit: 25 }),
    { revalidateOnFocus: false },
  )
  const [exporting, setExporting] = useState(false)

  if (isLoading) return <TabSkeleton rows={4} />

  const decisions = data?.decisions ?? []

  const handleExport = async () => {
    if (!isAdmin) return
    setExporting(true)
    try {
      const bundle = await enterpriseApi.exportTransparencyLogs()
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `transparency-logs-${new Date().toISOString().slice(0, 10)}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${bundle.summary?.decisionCount ?? 0} decision records`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed")
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ScrollText className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">AI decision transparency</CardTitle>
              </div>
              <CardDescription>
                EU AI Act–aligned records of automated operator decisions: input context, model, tools
                invoked, human overrides, and outcomes.
              </CardDescription>
            </div>
            {isAdmin && (
              <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
                <Download className="mr-2 h-4 w-4" />
                {exporting ? "Exporting…" : "Export JSON"}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No automated decision logs yet. Logs are created when operators auto-execute plan steps.
            </p>
          ) : (
            decisions.map((entry) => (
              <div key={entry.id} className="rounded-lg border border-border p-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusIcon status={entry.status} />
                    <span className="text-sm font-medium text-foreground">
                      {(entry.inputContext?.stepTitle as string) ||
                        (entry.inputContext?.planTitle as string) ||
                        entry.decisionSource}
                    </span>
                  </div>
                  <Badge variant="secondary" className={cn("capitalize", STATUS_STYLE[entry.status] ?? "")}>
                    {entry.status.replace("_", " ")}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {(entry.inputContext?.planSummary as string) || "Automated decision"}
                </p>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>{new Date(entry.createdAt).toLocaleString()}</span>
                  {entry.modelInfo?.model ? <span>Model: {String(entry.modelInfo.model)}</span> : null}
                  <span>Tools: {entry.toolsInvoked?.length ?? 0}</span>
                  {entry.humanOverride ? <span>Human override recorded</span> : null}
                </div>
              </div>
            ))
          )}

          {!isAdmin && (
            <Alert>
              <Lock className="h-4 w-4" />
              <AlertTitle>Read-only</AlertTitle>
              <AlertDescription>
                Only organization admins can export transparency bundles. You can review recent decision
                records below.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-success" />
  if (status === "failed") return <AlertTriangle className="h-4 w-4 text-destructive" />
  if (status === "pending_approval") return <Clock className="h-4 w-4 text-amber-500" />
  return <ScrollText className="h-4 w-4 text-muted-foreground" />
}
