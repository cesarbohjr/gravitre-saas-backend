"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
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

  const { data, error, isLoading, mutate } = useSWR(
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

  useEffect(() => {
    setOffset(0)
  }, [selectedAction, selectedEntityType, selectedDateRange])

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
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">Audit Trail</h1>
              <p className="text-sm text-muted-foreground mt-1">Who did what, when, and the outcome</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => void handleExport("csv")}>
                <FileText className="h-3.5 w-3.5" />
                CSV
              </Button>
              <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => void handleExport("json")}>
                <FileJson className="h-3.5 w-3.5" />
                JSON
              </Button>
            </div>
            <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => void mutate()}>
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-secondary border border-border">
                <Clock className="h-3 w-3 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">{data?.total ?? 0} logs</span>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-secondary border border-border">
                <User className="h-3 w-3 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">{summaryData?.byUser?.length ?? 0} active users</span>
              </div>
            </div>

            <div className="flex items-center gap-2 ml-auto">
              <Select value={selectedDateRange} onValueChange={setSelectedDateRange}>
                <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary border-border">
                  <Calendar className="h-3 w-3 mr-2 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24h">Last 24 hours</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                </SelectContent>
              </Select>

              <Select value={selectedAction} onValueChange={setSelectedAction}>
                <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary border-border">
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

              <Select value={selectedEntityType} onValueChange={setSelectedEntityType}>
                <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary border-border">
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

              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Search events..."
                  className="pl-8 h-8 w-[200px] text-xs bg-secondary border-border"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5" />
            Failed to load audit logs.
          </div>
        )}

        <div className="flex-1 overflow-auto px-6 py-4">
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
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary mb-3">
                <Search className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">No events match your filters</p>
            </div>
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
