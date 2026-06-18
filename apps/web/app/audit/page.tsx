"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState, NoResultsState } from "@/components/gravitre/empty-state"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { useFreshnessTimestamp } from "@/hooks/use-freshness-timestamp"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAuth } from "@/lib/auth-context"
import { auditApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { AuditLog } from "@/types/api"
import { toast } from "sonner"
import {
  Search,
  AlertCircle,
  RefreshCw,
  Calendar,
  FileJson,
  FileText,
  User,
  Clock,
  FileText as EntityIcon,
} from "lucide-react"
function getRangeStart(range: string): string | undefined {
  const now = Date.now()
  if (range === "24h") return new Date(now - 24 * 60 * 60 * 1000).toISOString()
  if (range === "7d") return new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString()
  if (range === "30d") return new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString()
  return undefined
}

function formatAction(action: string): string {
  return action
    .replaceAll("_", " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "N/A"
  return parsed.toLocaleString()
}

export default function AuditPage() {
  const { user } = useAuth()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedAction, setSelectedAction] = useState<string>("all")
  const [selectedEntityType, setSelectedEntityType] = useState<string>("all")
  const [selectedDateRange, setSelectedDateRange] = useState<string>("7d")
  const [offset, setOffset] = useState(0)
  const limit = 50

  const fromDate = getRangeStart(selectedDateRange)
  const listKey = user
    ? ["audit/list", selectedAction, selectedEntityType, selectedDateRange, offset] as const
    : null
  const summaryKey = user ? ["audit/summary", selectedDateRange] as const : null
  const { updatedAt, markFresh } = useFreshnessTimestamp()

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    listKey,
    () =>
      auditApi.list({
        action: selectedAction !== "all" ? selectedAction : undefined,
        entity_type: selectedEntityType !== "all" ? selectedEntityType : undefined,
        from: fromDate,
        limit,
        offset,
      }),
    {
      fallbackData: { logs: [] as AuditLog[], total: 0, hasMore: false },
      revalidateOnFocus: false,
      onSuccess: markFresh,
    }
  )
  const { data: summaryData } = useSWR(summaryKey, () => auditApi.summary(selectedDateRange), {
    fallbackData: { byAction: {}, byUser: [], byEntityType: {} },
    revalidateOnFocus: false,
  })

  const logs = data?.logs ?? []

  const filteredLogs = useMemo(() => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return logs.filter((log) => {
        const description = String((log.details?.description as string | undefined) ?? "")
        return (
          String(log.action ?? "").toLowerCase().includes(query) ||
          String(log.user_name ?? "").toLowerCase().includes(query) ||
          String(log.user_email ?? "").toLowerCase().includes(query) ||
          String(log.entity_type ?? "").toLowerCase().includes(query) ||
          String(log.entity_name ?? "").toLowerCase().includes(query) ||
          String(log.entity_id ?? "").toLowerCase().includes(query) ||
          description.toLowerCase().includes(query)
        )
      })
    }
    return logs
  }, [logs, searchQuery])

  const actions = Object.keys(summaryData?.byAction ?? {}).sort()
  const entityTypes = Object.keys(summaryData?.byEntityType ?? {}).sort()

  const isUpgradeRequired =
    (error instanceof ApiError && error.status === 403) ||
    (error instanceof Error && /upgrade|forbidden|unauthorized/i.test(error.message))

  const auditErrorMessage = isUpgradeRequired
    ? "Audit logs require a plan with audit access. Upgrade your plan or contact support."
    : "Failed to load audit logs. Check your connection and try again."

  const hasActiveFilters =
    searchQuery.trim() !== "" || selectedAction !== "all" || selectedEntityType !== "all"

  async function handleExport(format: "csv" | "json") {
    try {
      const response = await auditApi.export(format, fromDate)
      if (!response.ok) {
        throw new Error(`Export failed (${response.status})`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = format === "csv" ? "audit-export.csv" : "audit-export.json"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${format.toUpperCase()}`)
    } catch (exportError) {
      console.error("[v0] Audit export failed:", exportError)
      toast.error("Failed to export audit logs")
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 px-4 md:px-6 pt-4 md:pt-6 pb-4 border-b border-border space-y-4">
          {/* Mobile: Stack header vertically */}
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg md:text-xl font-semibold text-foreground">Audit Trail</h1>
              <p className="text-xs md:text-sm text-muted-foreground mt-0.5">Who did what, when, and the outcome</p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Button variant="outline" size="sm" className="h-9 gap-2" onClick={() => void handleExport("csv")}>
                <FileText className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">CSV</span>
              </Button>
              <Button variant="outline" size="sm" className="h-9 gap-2" onClick={() => void handleExport("json")}>
                <FileJson className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">JSON</span>
              </Button>
              <Button variant="outline" size="sm" className="h-9 gap-2" onClick={() => void mutate()}>
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                <span className="hidden sm:inline">Refresh</span>
              </Button>
            </div>
          </div>

          {/* Stats Pills - Horizontal scroll on mobile */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4 md:mx-0 md:px-0 scrollbar-none">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-secondary border border-border shrink-0">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs font-medium text-foreground whitespace-nowrap">{data?.total ?? 0} logs</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-secondary border border-border shrink-0">
              <User className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs font-medium text-foreground whitespace-nowrap">{summaryData?.byUser?.length ?? 0} active users</span>
            </div>
          </div>

          {/* Filters - Stack on mobile, row on desktop */}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <Select
              value={selectedDateRange}
              onValueChange={(value) => {
                setSelectedDateRange(value)
                setOffset(0)
              }}
            >
              <SelectTrigger className="w-full sm:w-[140px] h-10 sm:h-8 text-sm sm:text-xs bg-secondary border-border">
                <Calendar className="h-3.5 w-3.5 mr-2 text-muted-foreground shrink-0" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={selectedAction}
              onValueChange={(value) => {
                setSelectedAction(value)
                setOffset(0)
              }}
            >
              <SelectTrigger className="w-full sm:w-[140px] h-10 sm:h-8 text-sm sm:text-xs bg-secondary border-border">
                <SelectValue placeholder="Action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All actions</SelectItem>
                {actions.map((action) => (
                  <SelectItem key={action} value={action}>
                    {formatAction(action)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={selectedEntityType}
              onValueChange={(value) => {
                setSelectedEntityType(value)
                setOffset(0)
              }}
            >
              <SelectTrigger className="w-full sm:w-[140px] h-10 sm:h-8 text-sm sm:text-xs bg-secondary border-border">
                <SelectValue placeholder="Entity Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All entities</SelectItem>
                {entityTypes.map((entityType) => (
                  <SelectItem key={entityType} value={entityType}>
                    {entityType}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative flex-1 sm:flex-initial sm:w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 sm:h-3.5 sm:w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search events..."
                className="pl-9 h-10 sm:h-8 text-sm sm:text-xs bg-secondary border-border"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="mx-4 md:mx-6 mt-4 flex items-center justify-between gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <span className="flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {auditErrorMessage}
            </span>
            {!isUpgradeRequired && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1.5 text-destructive hover:text-destructive"
                onClick={() => void mutate()}
              >
                <RefreshCw className="h-3 w-3" />
                Retry
              </Button>
            )}
          </div>
        )}

        <div className="flex-1 overflow-auto px-4 md:px-6 py-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {filteredLogs.length} event{filteredLogs.length === 1 ? "" : "s"}
            </span>
            <DataFreshness
              updatedAt={updatedAt}
              isRefreshing={isValidating}
              onRefresh={() => void mutate()}
            />
          </div>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4 animate-pulse">
                  <div className="h-10 w-10 rounded-full bg-secondary" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-48 bg-secondary rounded" />
                    <div className="h-3 w-full bg-secondary rounded" />
                    <div className="h-3 w-32 bg-secondary rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredLogs.length === 0 ? (
            hasActiveFilters ? (
              <NoResultsState
                onClear={() => {
                  setSearchQuery("")
                  setSelectedAction("all")
                  setSelectedEntityType("all")
                }}
              />
            ) : (
              <EmptyState
                icon={Search}
                title="No audit events yet"
                description="Activity across your workspace will be recorded here."
              />
            )
          ) : (
            <div className="space-y-3">
              {filteredLogs.map((log, index) => (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.03, 0.25) }}
                  className="rounded-lg border border-border bg-card/60 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-foreground">{formatAction(log.action)}</p>
                      <p className="text-xs text-muted-foreground">
                        {log.user_name || log.user_email || "System"} · {formatTime(log.created_at)}
                      </p>
                    </div>
                    <span className="rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] uppercase text-muted-foreground">
                      {log.entity_type}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1">
                      <EntityIcon className="h-3 w-3 text-muted-foreground" />
                      <span className="text-foreground">{log.entity_name || log.entity_id}</span>
                    </span>
                    {log.user_email && (
                      <span className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1">
                        <User className="h-3 w-3 text-muted-foreground" />
                        <span className="text-foreground">{log.user_email}</span>
                      </span>
                    )}
                    {log.ip_address && (
                      <span className="inline-flex items-center rounded-md bg-secondary px-2 py-1 text-foreground">
                        {log.ip_address}
                      </span>
                    )}
                  </div>
                  {log.details && Object.keys(log.details).length > 0 && (
                    <div className="mt-3 rounded-md border border-border/60 bg-background/50 p-2">
                      <p className="text-[10px] uppercase text-muted-foreground mb-1">Details</p>
                      <pre className="text-[11px] text-muted-foreground overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {filteredLogs.length > 0 && (
          <div className="flex-shrink-0 border-t border-border px-6 py-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Showing {filteredLogs.length} logs (offset {offset}) · total {data?.total ?? 0}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset((current) => Math.max(0, current - limit))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data?.hasMore}
                  onClick={() => setOffset((current) => current + limit)}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
