"use client"

import { useId, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, NoResultsState } from "@/components/gravitre/empty-state"
import { Illustration } from "@/components/gravitre/illustration"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import {
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
  FileText as EntityIcon,
} from "lucide-react"
import { categorizeAuditEvent } from "@/lib/audit-category"
import {
  formatAuditActionLabel,
  formatAuditEntityLabel,
  summarizeAuditLog,
} from "@/lib/audit-summary"

const EMPTY_LOGS: AuditLog[] = []

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
  const [exporting, setExporting] = useState(false)
  const exportInFlight = useRef(false)
  const limit = 50

  const fromDate = getRangeStart(selectedDateRange)
  const listKey = user
    ? (["audit/list", user.id, selectedAction, selectedEntityType, selectedDateRange, offset] as const)
    : null
  const summaryKey = user ? (["audit/summary", user.id, selectedDateRange] as const) : null

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    listKey,
    async () => ({
      ...await auditApi.list({
        action: selectedAction !== "all" ? selectedAction : undefined,
        entity_type: selectedEntityType !== "all" ? selectedEntityType : undefined,
        from: fromDate,
        limit,
        offset,
      }),
      fetchedAt: Date.now(),
    }),
    {
      revalidateOnFocus: false,
    },
  )
  const { data: summaryData, error: summaryError, isLoading: summaryLoading, mutate: refreshSummary } = useSWR(summaryKey, () => auditApi.summary(selectedDateRange), {
    revalidateOnFocus: false,
  })

  const logs = data?.logs ?? EMPTY_LOGS

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

  const isAccessDenied = error instanceof ApiError && (error.status === 401 || error.status === 403)

  const auditErrorMessage = isAccessDenied
    ? "Audit access is unavailable. Check your session, organization permissions, and plan access."
    : "Failed to load audit logs. Check your connection and try again."

  const hasActiveFilters =
    searchQuery.trim() !== "" || selectedAction !== "all" || selectedEntityType !== "all"

  async function handleExport(format: "csv" | "json") {
    if (exportInFlight.current) return
    exportInFlight.current = true
    setExporting(true)
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
    } finally {
      exportInFlight.current = false
      setExporting(false)
    }
  }

  if (!user) return <AppShell><p className="p-6 text-sm">Sign in to view your audit trail.</p></AppShell>

  return (
    <AppShell>
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]" data-composition="operate">
        <GravitrePageHeader
          className="shrink-0"
          eyebrow="Governance"
          title="Audit trail"
          family="operating"
          description="Who did what, when, and the outcome"
          icon={<NavFile className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <DataFreshness
                updatedAt={data?.fetchedAt ?? null}
                isRefreshing={isValidating}
              />
              <Button
                variant="outline"
                size="sm"
                className="min-h-11 gap-2"
                aria-label="Export audit CSV"
                disabled={!user || exporting}
                onClick={() => void handleExport("csv")}
              >
                <FileText className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">CSV</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="min-h-11 gap-2"
                aria-label="Export audit JSON"
                disabled={!user || exporting}
                onClick={() => void handleExport("json")}
              >
                <FileJson className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">JSON</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="min-h-11 gap-2"
                aria-label="Refresh audit events"
                disabled={isValidating}
                onClick={() => { void mutate(); void refreshSummary() }}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isValidating ? "animate-spin motion-reduce:animate-none" : ""}`} />
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
                <SelectTrigger aria-label="Audit range" className="min-h-11 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
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
                <SelectTrigger aria-label="Audit action" className="min-h-11 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
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
                <SelectTrigger aria-label="Audit entity" className="min-h-11 w-[140px] border-divide bg-[color:var(--g-surface-1)] text-xs">
                  <SelectValue placeholder="Entity type" />
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
                aria-label="Search loaded audit events"
                placeholder="Search this page..."
                className="min-h-11 border-divide bg-[color:var(--g-surface-1)] pl-9 text-xs"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </HubFilterBar>
        </GravitrePageHeader>

        {error && (
          <div role="alert" className="mx-[var(--np-page-pad-sm)] mt-3 flex flex-wrap items-center justify-between gap-2 rounded-[var(--np-radius-lg)] border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive sm:mx-[var(--np-page-pad)]">
            <span className="flex min-w-0 items-start gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {auditErrorMessage}
            </span>
            {!isAccessDenied && (
              <Button
                variant="ghost"
                size="sm"
                className="min-h-11 gap-1.5 text-destructive hover:text-destructive"
                onClick={() => void mutate()}
              >
                <RefreshCw className="h-3 w-3" />
                Retry
              </Button>
            )}
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col gap-[var(--np-kpi-gap)] overflow-auto px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-3.5">
          <section
            aria-label="Audit summary"
            className="flex shrink-0 flex-wrap items-baseline gap-x-6 gap-y-2 border-b border-divide pb-3"
          >
            <dl className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div className="flex items-baseline gap-2">
                <dt className="text-xs text-muted-foreground">Matching events</dt>
                <dd className="text-sm font-semibold tabular-nums text-foreground">
                  {isLoading ? "—" : error || !Number.isFinite(data?.total) ? "Not reported" : data?.total}
                </dd>
              </div>
              <div className="flex items-baseline gap-2">
                <dt className="text-xs text-muted-foreground">Active users</dt>
                <dd className="text-sm font-semibold tabular-nums text-foreground">
                  {summaryLoading ? "—" : summaryError || !Array.isArray(summaryData?.byUser) ? "Not reported" : summaryData.byUser.length}
                </dd>
              </div>
            </dl>
            <p className="text-xs text-muted-foreground sm:ml-auto">
              Search covers the loaded page of up to {limit}. Exports cover the whole date range.
            </p>
          </section>
          {summaryError && <div role="alert" className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
            <p>Could not load audit summary. Event results are separate.</p>
            <Button variant="outline" className="min-h-11" onClick={() => void refreshSummary()}>Retry summary</Button>
          </div>}
          {isLoading ? (
            <div role="status" aria-label="Loading audit events" className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="flex animate-pulse gap-4 motion-reduce:animate-none rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]"
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
            error ? (
              <Illustration name="moment-error" width={170} className="mx-auto mt-8" />
            ) : (hasActiveFilters ? (
              <NoResultsState
                onClear={() => {
                  setSearchQuery("")
                  setSelectedAction("all")
                  setSelectedEntityType("all")
                }}
              />
            ) : (
              <EmptyState
                illustration="moment-focus-time"
                title="No audit events yet"
                description="No events were reported for the selected date range."
              />
            ))
          ) : (
            <div className="overflow-hidden rounded-xl border border-divide bg-[color:var(--g-surface-1)]">
              {filteredLogs.map((log) => (
                <AuditLogCard key={log.id} log={log} />
              ))}
            </div>
          )}
        </div>

        {(offset > 0 || (data && (logs.length > 0 || data.hasMore))) && (
          <div className="shrink-0 border-t border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Page {Math.floor(offset / limit) + 1} · {isLoading ? "Loading events" : error ? "Results unavailable" : `${logs.length} loaded · ${filteredLogs.length} matching search`} · total {error || !Number.isFinite(data?.total) ? "Not reported" : data?.total}
              </p>
              <div className="flex min-w-0 items-start gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-11"
                  disabled={offset === 0 || isLoading || isValidating}
                  onClick={() => setOffset((current) => Math.max(0, current - limit))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-11"
                  disabled={!data?.hasMore || isLoading || isValidating || !!error}
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

function AuditLogCard({ log }: { log: AuditLog }) {
  const reduceMotion = useReducedMotion()
  const technicalId = useId()
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
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: reduceMotion ? 0 : 0.18 }}
      className="min-w-0 border-b border-divide p-4 last:border-b-0 [overflow-wrap:anywhere]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex min-w-0 items-start gap-2">
            <span
              className={cn(
                "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--np-radius-md)]",
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
        <span className="inline-flex items-center gap-1 rounded-[var(--np-radius-md)] max-w-full bg-[color:var(--g-surface-2)] px-2 py-1">
          <EntityIcon className="h-3 w-3 text-muted-foreground" />
          <span className="text-foreground">{entityLabel}</span>
        </span>
        {log.user_email ? (
          <span className="inline-flex items-center gap-1 rounded-[var(--np-radius-md)] max-w-full bg-[color:var(--g-surface-2)] px-2 py-1">
            <User className="h-3 w-3 text-muted-foreground" />
            <span className="text-foreground">{log.user_email}</span>
          </span>
        ) : null}
      </div>

      {hasTechnicalDetails ? (
        <div className="mt-3">
          <button
            type="button"
            aria-expanded={showTechnical}
            aria-controls={technicalId}
            onClick={() => setShowTechnical((open) => !open)}
            className="inline-flex min-h-11 items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {showTechnical ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showTechnical ? "Hide technical details" : "Show technical details"}
          </button>
          {showTechnical ? (
            <pre id={technicalId} className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-2 text-[11px] text-muted-foreground">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </motion.div>
  )
}
