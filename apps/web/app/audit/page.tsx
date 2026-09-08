"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { NoResultsState } from "@/components/gravitre/empty-state"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { HubFilterBar, HubFilterField } from "@/components/gravitre/hub-filter-bar"
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
import { useOrgAdmin } from "@/lib/use-org-admin"
import { auditApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { AuditLog } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { NucleoSearch } from "@/components/icons/nucleo/semantic"
import { NavFile } from "@/components/icons/nodus-nav/outline"
import {
  AlertCircle,
  RefreshCw,
  Calendar,
  ChevronDown,
  ChevronUp,
  FileJson,
  FileText,
  User,
  Clock,
  FileText as EntityIcon,
} from "lucide-react"
import { categorizeAuditEvent } from "@/lib/audit-category"
import {
  formatAuditActionLabel,
  formatAuditEntityLabel,
  summarizeAuditLog,
} from "@/lib/audit-summary"

function getRangeStart(range: string): string | undefined {
  const now = Date.now()
  if (range === "24h") return new Date(now - 24 * 60 * 60 * 1000).toISOString()
  if (range === "7d") return new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString()
  if (range === "30d") return new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString()
  return undefined
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "N/A"
  return parsed.toLocaleString()
}

export default function AuditPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedAction, setSelectedAction] = useState<string>("all")
  const [selectedEntityType, setSelectedEntityType] = useState<string>("all")
  const [selectedDateRange, setSelectedDateRange] = useState<string>("7d")
  const [offset, setOffset] = useState(0)
  const limit = 50

  const fromDate = getRangeStart(selectedDateRange)
  const listKey = user
    ? (["audit/list", selectedAction, selectedEntityType, selectedDateRange, offset] as const)
    : null
  const summaryKey = user ? (["audit/summary", selectedDateRange] as const) : null

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
    },
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
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          className="shrink-0"
          eyebrow="Governance"
          title="Audit Trail"
          description="Who did what, when, and the outcome"
          icon={<NavFile className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <DataFreshness
                updatedAt={data ? Date.now() : null}
                isRefreshing={isValidating}
                onRefresh={() => void mutate()}
              />
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={() => void handleExport("csv")}
              >
                <FileText className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">CSV</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={() => void handleExport("json")}
              >
                <FileJson className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">JSON</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={() => void mutate()}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                <span className="hidden sm:inline">Refresh</span>
              </Button>
            </div>
          }
        >
          {isAdmin ? (
            <p className="mb-3 max-w-2xl rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">For admins:</span> this is the org
              compliance surface — export CSV/JSON for reviews, filter by actor and action, and
              verify writes that chat confirmed. Also linked from Settings and every chat reply that
              ran tools.
            </p>
          ) : null}

          <HubFilterBar compact className="mt-1">
            <HubFilterField label="Range" compact>
              <Select
                value={selectedDateRange}
                onValueChange={(value) => {
                  setSelectedDateRange(value)
                  setOffset(0)
                }}
              >
                <SelectTrigger className="h-8 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
                  <Calendar className="mr-2 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24h">Last 24 hours</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                </SelectContent>
              </Select>
            </HubFilterField>

            <HubFilterField label="Action" compact>
              <Select
                value={selectedAction}
                onValueChange={(value) => {
                  setSelectedAction(value)
                  setOffset(0)
                }}
              >
                <SelectTrigger className="h-8 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
                  <SelectValue placeholder="Action" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actions</SelectItem>
                  {actions.map((action) => (
                    <SelectItem key={action} value={action}>
                      {formatAuditActionLabel(action)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </HubFilterField>

            <HubFilterField label="Entity" compact>
              <Select
                value={selectedEntityType}
                onValueChange={(value) => {
                  setSelectedEntityType(value)
                  setOffset(0)
                }}
              >
                <SelectTrigger className="h-8 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
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
            </HubFilterField>

            <div className="relative min-w-[180px] flex-1 sm:max-w-[220px]">
              <NucleoSearch className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search events..."
                className="h-8 border-divide bg-[color:var(--g-surface-1)] pl-9 text-xs"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </HubFilterBar>
        </GravitrePageHeader>

        {error && (
          <div className="mx-[var(--np-page-pad-sm)] mt-3 flex items-center justify-between gap-2 rounded-[var(--np-radius-lg)] border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive sm:mx-[var(--np-page-pad)]">
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

        <div className="flex min-h-0 flex-1 flex-col gap-[var(--np-kpi-gap)] overflow-auto px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-3.5">
          <section className="grid shrink-0 grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric
              label="Logs"
              value={isLoading ? "—" : (data?.total ?? 0)}
              hint={isLoading ? "Loading" : "In selected range"}
              icon={<Clock className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Active users"
              value={summaryData?.byUser?.length ?? 0}
              hint="In selected range"
              icon={<User className="h-4 w-4" />}
            />
            <GravitreMetric
              label="In view"
              value={filteredLogs.length}
              hint="After filters"
              icon={<EntityIcon className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Offset"
              value={offset}
              hint={`Page size ${limit}`}
              icon={<FileText className="h-4 w-4" />}
            />
          </section>

          <div className="mb-0 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {filteredLogs.length} event{filteredLogs.length === 1 ? "" : "s"}
            </span>
          </div>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="flex animate-pulse gap-4 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]"
                >
                  <div className="h-10 w-10 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)]" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-48 rounded bg-[color:var(--g-surface-2)]" />
                    <div className="h-3 w-full rounded bg-[color:var(--g-surface-2)]" />
                    <div className="h-3 w-32 rounded bg-[color:var(--g-surface-2)]" />
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
              <GravitreEmpty
                icon={<NucleoSearch className="h-5 w-5" />}
                title="No audit events yet"
                hint="Activity across your workspace will be recorded here."
              />
            )
          ) : (
            <div className="space-y-3">
              {filteredLogs.map((log, index) => (
                <AuditLogCard key={log.id} log={log} index={index} />
              ))}
            </div>
          )}
        </div>

        {filteredLogs.length > 0 && (
          <div className="shrink-0 border-t border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
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

function AuditLogCard({ log, index }: { log: AuditLog; index: number }) {
  const [showTechnical, setShowTechnical] = useState(false)
  const category = categorizeAuditEvent({
    action: log.action,
    entityType: log.entity_type,
    category: typeof log.details?.category === "string" ? log.details.category : null,
  })
  const CategoryIcon = category.icon
  const summary = summarizeAuditLog(log)
  const entityLabel = formatAuditEntityLabel(log)
  const hasTechnicalDetails = Boolean(log.details && Object.keys(log.details).length > 0)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.25) }}
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide border-l-4 bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]",
        category.edge,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-[var(--np-radius-md)]",
                category.soft,
              )}
            >
              <CategoryIcon className={cn("h-3.5 w-3.5", category.text)} />
            </span>
            <p className="text-sm font-semibold text-foreground">
              {formatAuditActionLabel(log.action)}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            {log.user_name || log.user_email || "System"} · {formatTime(log.created_at)}
          </p>
        </div>
        <span className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-2 py-0.5 text-[10px] uppercase text-muted-foreground">
          {summary.categoryLabel}
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-foreground">{summary.summary}</p>

      {summary.outcome ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Outcome: <span className="font-medium text-foreground">{summary.outcome}</span>
        </p>
      ) : null}

      {summary.bullets.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
          {summary.bullets.map((bullet) => (
            <li key={bullet} className="flex gap-2">
              <span className="text-muted-foreground/60">•</span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-2 py-1">
          <EntityIcon className="h-3 w-3 text-muted-foreground" />
          <span className="text-foreground">{entityLabel}</span>
        </span>
        {log.user_email ? (
          <span className="inline-flex items-center gap-1 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-2 py-1">
            <User className="h-3 w-3 text-muted-foreground" />
            <span className="text-foreground">{log.user_email}</span>
          </span>
        ) : null}
      </div>

      {hasTechnicalDetails ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowTechnical((open) => !open)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
          >
            {showTechnical ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showTechnical ? "Hide technical details" : "Show technical details"}
          </button>
          {showTechnical ? (
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-2 text-[11px] text-muted-foreground">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </motion.div>
  )
}
