"use client"

import { useState } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { sourceTypeVendorKey } from "@/lib/brand-vendor"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { HIGHLIGHT } from "@/lib/design-system"
import {
  Plus,
  Database,
  Workflow,
  RefreshCw,
  Loader2,
  ExternalLink,
  Table2,
  Clock,
  ChevronDown,
} from "lucide-react"
import { ApiError, fetcher as apiFetcher, PlanRequiredApiError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { sourcesApi } from "@/lib/api"
import { buildWorkflowFromSourceUrl } from "@/lib/source-workflow-handoff"
import type { CreateSourceRequest } from "@/types/api"
import { AddDataSourceModal } from "@/components/gravitre/add-data-source-modal"
import { EmptyState, NoResultsState } from "@/components/gravitre/empty-state"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { toast } from "sonner"

interface Source {
  id: string
  name: string
  type: string
  category: "sql" | "nosql" | "warehouse"
  status: "connected" | "disconnected" | "error" | "syncing"
  environment: "production" | "staging"
  lastSync: string
  lastSyncAt: number | null
  tables: number
  records: string
  description: string
  workflowsUsing: number
  operatorsUsing: number
  health: number // 0-100
  topTables?: string[]
}

function inferCategory(type: string): Source["category"] {
  const normalized = type.toLowerCase()
  if (normalized.includes("postgres") || normalized.includes("mysql")) return "sql"
  if (normalized.includes("mongo")) return "nosql"
  return "warehouse"
}

function formatRelativeSync(iso: string | null | undefined): string {
  if (!iso) return "Never"
  const timestamp = new Date(iso)
  if (Number.isNaN(timestamp.getTime())) return "Never"
  const diffMs = Date.now() - timestamp.getTime()
  const minutes = Math.max(0, Math.floor(diffMs / 60000))
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

function formatCompactCount(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0"
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function normalizeSource(input: Record<string, unknown>): Source {
  const status = String(input.status ?? "connected")
  const type = String(input.type ?? "Unknown")
  const rawRecordCount = Number(
    input.recordCount ?? input.record_count ?? input.recordsCount ?? input.records_count ?? 0
  )
  const stringRecords = String(input.records ?? "")
  const parsedStringRecords = Number.parseFloat(stringRecords.replace(/[^\d.]/g, ""))
  const recordsFromString = stringRecords.includes("M")
    ? parsedStringRecords * 1_000_000
    : stringRecords.includes("K")
    ? parsedStringRecords * 1_000
    : parsedStringRecords
  const effectiveRecordCount =
    Number.isFinite(rawRecordCount) && rawRecordCount > 0
      ? rawRecordCount
      : Number.isFinite(recordsFromString)
      ? recordsFromString
      : 0
  const environment = String(input.environment ?? "production")
  const rawLastSync =
    (input.lastSync as string | null) ?? (input.last_sync as string | null) ?? (input.lastSyncAt as string | null)
  const lastSyncMs = rawLastSync ? new Date(rawLastSync).getTime() : Number.NaN
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "source"),
    type,
    category:
      input.category === "sql" || input.category === "nosql" || input.category === "warehouse"
        ? input.category
        : inferCategory(type),
    status:
      status === "disconnected" || status === "error" || status === "syncing"
        ? status
        : "connected",
    environment: environment === "staging" ? "staging" : "production",
    lastSync: formatRelativeSync(rawLastSync),
    lastSyncAt: Number.isFinite(lastSyncMs) ? lastSyncMs : null,
    tables: Number(input.tables ?? input.tablesCount ?? input.tables_count ?? 0),
    records: formatCompactCount(effectiveRecordCount),
    description: String(input.description ?? `${type} data source`),
    workflowsUsing: Number(input.workflowsUsing ?? input.workflows_using ?? 0),
    operatorsUsing: Number(input.operatorsUsing ?? input.operators_using ?? 0),
    health:
      Number.isFinite(Number(input.health)) && Number(input.health) > 0
        ? Number(input.health)
        : status === "error" || status === "disconnected"
        ? 0
        : status === "syncing"
        ? 85
        : 98,
    topTables: Array.isArray(input.topTables) ? (input.topTables as string[]) : [],
  }
}

function normalizeSourcesResponse(payload: unknown): Source[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.sources) ? model.sources : null
  if (!raw) return []
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeSource(item))
    .filter((item) => item.id.length > 0)
  return normalized
}

const categoryLabels = {
  sql: "SQL Databases",
  nosql: "NoSQL",
  warehouse: "Data Warehouses",
}

// Health ring component
function HealthRing({ health, size = 40 }: { health: number; size?: number }) {
  const radius = (size - 4) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (health / 100) * circumference
  
  const color = health >= 90 ? "stroke-emerald-500" : health >= 70 ? "stroke-amber-500" : "stroke-red-500"
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={3}
          fill="none"
          className="stroke-secondary"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={3}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn("transition-all duration-500", color)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-foreground">
        {health}%
      </span>
    </div>
  )
}

// Data source tile with hierarchy preview - Premium
function SourceTile({ 
  source, 
  isExpanded,
  onToggle,
  index,
  onSync,
  onDelete,
  isMutating,
}: { 
  source: Source
  isExpanded: boolean
  onToggle: () => void
  index: number
  onSync: (sourceId: string) => Promise<void>
  onDelete: (sourceId: string) => Promise<void>
  isMutating: boolean
}) {
  const router = useRouter()

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={cn(
        "group relative overflow-hidden rounded-[var(--np-radius-lg)] border transition-all duration-300",
        source.status === "error"
          ? "border-destructive/30 bg-[color:var(--g-surface-1)]"
          : "border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] hover:border-[color:var(--g-brand-border)]",
        source.status === "syncing" && "border-[color:var(--g-signal)]/40",
      )}
    >
      <div
        className={cn(
          "absolute top-0 left-0 right-0 h-0.5",
          source.status === "connected" && "bg-[color:var(--g-brand)]",
          source.status === "syncing" && "bg-[color:var(--g-signal)]",
          source.status === "error" && "bg-destructive",
          source.status === "disconnected" && "bg-muted-foreground/40",
        )}
      />

      <div className="relative p-5" onClick={onToggle}>
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <ConnectorIcon
              vendor={sourceTypeVendorKey(source.type)}
              name={source.name}
              size="md"
              showStatusIndicator={false}
            />
            <div>
              <h3 className="text-sm font-semibold text-foreground">{source.name}</h3>
              <p className="text-xs text-muted-foreground">{source.type}</p>
            </div>
          </div>
          <HealthRing health={source.health} />
        </div>

        <div className="mb-4 flex items-center gap-2">
          <span
            className={cn(
              "rounded-[4px] px-1.5 py-0.5 text-[11px] font-medium capitalize",
              source.status === "connected" && HIGHLIGHT.brand,
              source.status === "syncing" && HIGHLIGHT.signal,
              source.status === "error" && HIGHLIGHT.danger,
              source.status === "disconnected" && HIGHLIGHT.neutral,
            )}
          >
            {source.status}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="h-2.5 w-2.5" />
            {source.lastSync}
          </span>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="border-l border-divide pl-3 text-left">
            <div className="mb-1 flex items-center gap-1 text-muted-foreground">
              <Table2 className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.tables}</p>
            <p className="text-[11px] text-muted-foreground">tables</p>
          </div>
          <div className="border-l border-divide pl-3 text-left">
            <div className="mb-1 flex items-center gap-1 text-muted-foreground">
              <Database className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.records}</p>
            <p className="text-[11px] text-muted-foreground">records</p>
          </div>
          <div className="border-l border-divide pl-3 text-left">
            <div className="mb-1 flex items-center gap-1 text-muted-foreground">
              <Workflow className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.workflowsUsing}</p>
            <p className="text-[11px] text-muted-foreground">workflows</p>
          </div>
        </div>

        {/* Table preview */}
        {source.topTables && (
          <div className="mb-3">
            <div className="flex items-center gap-1 flex-wrap">
              {source.topTables.slice(0, 3).map((table) => (
                <span 
                  key={table}
                  className="rounded-[3px] border border-divide px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
                >
                  {table}
                </span>
              ))}
              {source.topTables.length > 3 && (
                <span className="text-[10px] text-muted-foreground">
                  +{source.topTables.length - 3} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Expand toggle */}
        <button 
          className="w-full flex items-center justify-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors py-1"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
        >
          {isExpanded ? "Less" : "More"}
          <ChevronDown className={cn("h-3 w-3 transition-transform", isExpanded && "rotate-180")} />
        </button>
      </div>

      {/* Expanded details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border"
          >
            <div className="p-4 space-y-3">
              <p className="text-xs text-muted-foreground">{source.description}</p>
              
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  {source.operatorsUsing} operators
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs flex-1"
                  onClick={() => router.push(`/sources/${source.id}`)}
                >
                  <ExternalLink className="h-3 w-3" />
                  Details
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs flex-1"
                  onClick={() => router.push(buildWorkflowFromSourceUrl({ id: source.id, name: source.name, type: source.type }))}
                >
                  <Workflow className="h-3 w-3" />
                  Use
                </Button>
                <Button 
                  size="sm" 
                  className="h-7 gap-1.5 text-xs"
                  onClick={() => void onSync(source.id)}
                  disabled={isMutating}
                >
                  {isMutating ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  Sync
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1.5 text-xs text-red-600 dark:text-red-400 border-red-500/30 hover:bg-red-500/10"
                  onClick={() => void onDelete(source.id)}
                  disabled={isMutating}
                >
                  Delete
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// Add Source Modal — see components/gravitre/add-data-source-modal.tsx

const SOURCES_TITLE = "Sources"
const SOURCES_DESCRIPTION = "Connected databases and warehouses your agents and workflows can query."

export default function SourcesPage() {
  const { user } = useAuth()
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [mutatingSourceId, setMutatingSourceId] = useState<string | null>(null)
  const [isCreatingSource, setIsCreatingSource] = useState(false)
  const { data, error, isLoading, isValidating, mutate } = useSWR(user ? "/api/sources" : null, apiFetcher, {
    fallbackData: { sources: [] as Source[] },
    revalidateOnFocus: false,
    onError: (err) => console.error("[v0] Sources fetch error:", err),
  })
  const sources = normalizeSourcesResponse(data)

  const handleSync = async (sourceId: string) => {
    try {
      setMutatingSourceId(sourceId)
      await sourcesApi.sync(sourceId)
      toast.success("Sync started")
      await mutate()
    } catch (err) {
      console.error("[v0] Sync failed:", err)
      toast.error("Sync failed")
    } finally {
      setMutatingSourceId((current) => (current === sourceId ? null : current))
    }
  }

  const handleDelete = async (sourceId: string) => {
    if (!window.confirm("Delete this source?")) return
    try {
      setMutatingSourceId(sourceId)
      await sourcesApi.delete(sourceId)
      toast.success("Source deleted")
      await mutate()
      if (expandedSource === sourceId) {
        setExpandedSource(null)
      }
    } catch (err) {
      console.error("[v0] Delete failed:", err)
      toast.error("Failed to delete")
    } finally {
      setMutatingSourceId((current) => (current === sourceId ? null : current))
    }
  }

  const handleCreate = async (payload: CreateSourceRequest) => {
    try {
      setIsCreatingSource(true)
      await sourcesApi.create(payload)
      toast.success("Source created")
      await mutate()
    } catch (err) {
      console.error("[v0] Create failed:", err)
      toast.error("Failed to create source")
      throw err
    } finally {
      setIsCreatingSource(false)
    }
  }

  const groupedSources = sources.reduce(
    (acc, source) => {
      if (!acc[source.category]) acc[source.category] = []
      acc[source.category].push(source)
      return acc
    },
    {} as Record<string, Source[]>,
  )

  const categories = Object.keys(groupedSources) as (keyof typeof categoryLabels)[]
  const connectedCount = sources.filter((s) => s.status === "connected" || s.status === "syncing").length
  const errorCount = sources.filter((s) => s.status === "error").length
  const totalRecords = sources.reduce((acc, s) => {
    const num = parseFloat(s.records.replace(/[KM]/g, ""))
    const multiplier = s.records.includes("M") ? 1000000 : s.records.includes("K") ? 1000 : 1
    return acc + (Number.isFinite(num) ? num * multiplier : 0)
  }, 0)
  const totalTables = sources.reduce((a, s) => a + s.tables, 0)

  const needsAttention = sources.filter((s) => s.status === "error" || s.status === "disconnected")
  const recentIngestion = [...sources]
    .filter((s) => s.lastSyncAt !== null || s.status === "syncing")
    .sort((a, b) => (b.lastSyncAt ?? Number.MAX_SAFE_INTEGER) - (a.lastSyncAt ?? Number.MAX_SAFE_INTEGER))
    .slice(0, 5)
  // The shell's trial/plan strip already carries entitlement errors; repeating it inline is noise.
  const showInlineError =
    Boolean(error) && !(error instanceof PlanRequiredApiError) && !(error instanceof ApiError && error.status === 402)

  return (
    <AppShell title={SOURCES_TITLE}>
      <div data-testid="sources-hub-b">
        <GravitrePageHeader
          title={SOURCES_TITLE}
          description={SOURCES_DESCRIPTION}
          status={
            sources.length > 0 ? (
              <span className="flex flex-wrap items-center gap-x-4 gap-y-1" data-testid="sources-health-line">
                <LiveStatus tone={errorCount > 0 ? "attention" : "live"}>
                  <span>
                    <span className="font-semibold tabular-nums text-[color:var(--g-text-primary)]">{connectedCount}</span>
                    {" of "}
                    <span className="tabular-nums">{sources.length}</span> connected
                  </span>
                </LiveStatus>
                <span className={cn(errorCount > 0 && "font-medium text-destructive")}>
                  <span className="tabular-nums">{errorCount}</span> {errorCount === 1 ? "error" : "errors"}
                </span>
                <span>
                  <span className="tabular-nums">{formatCompactCount(totalRecords)}</span> records ·{" "}
                  <span className="tabular-nums">{totalTables}</span> tables
                </span>
              </span>
            ) : null
          }
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("mr-1 h-4 w-4", isValidating && "animate-spin")} />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setAddModalOpen(true)} disabled={isLoading}>
                <Plus className="mr-1 h-4 w-4" />
                Add source
              </Button>
            </div>
          }
        />

        <div className="grid gap-8 px-[var(--np-page-pad-sm)] pb-8 pt-2 sm:px-[var(--np-page-pad)] lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="min-w-0 space-y-6">
            {showInlineError ? (
              <div className="flex items-center justify-between gap-3 border-l-2 border-destructive bg-background py-1.5 pl-3 text-[13px] text-foreground">
                <span>{error instanceof Error ? error.message : "Failed to load sources"}</span>
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => mutate()}>
                  Retry
                </Button>
              </div>
            ) : null}

            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[color:var(--g-border-default)]">
              <div className="-mb-px flex flex-wrap items-center gap-5" role="tablist" aria-label="Source category">
                {[null, ...categories].map((cat) => {
                  const active = selectedCategory === cat
                  return (
                    <button
                      key={cat ?? "all"}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      onClick={() => setSelectedCategory(cat)}
                      className={cn(
                        "border-b-2 pb-2 text-[13px] font-medium transition-colors",
                        active
                          ? "border-[color:var(--g-text-primary)] text-[color:var(--g-text-primary)]"
                          : "border-transparent text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {cat ? categoryLabels[cat] : "All sources"}
                    </button>
                  )
                })}
              </div>
              <div className="pb-2">
                <DataFreshness
                  updatedAt={data ? Date.now() : null}
                  isRefreshing={isValidating}
                  onRefresh={() => mutate()}
                />
              </div>
            </div>

            {isLoading && sources.length === 0 ? (
              <div className="h-40 animate-pulse rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)]" />
            ) : null}

            {!isLoading && !error && sources.length === 0 ? (
              <EmptyState
                icon={Database}
                title="No data sources yet"
                description="Connect your first data source to ground your agents in real business data."
                action={{ label: "Add data source", onClick: () => setAddModalOpen(true) }}
              />
            ) : null}

            {!isLoading &&
            sources.length > 0 &&
            categories.filter((cat) => selectedCategory === null || cat === selectedCategory).length === 0 ? (
              <NoResultsState onClear={() => setSelectedCategory(null)} />
            ) : null}

            <AnimatePresence mode="wait">
              {categories
                .filter((cat) => selectedCategory === null || cat === selectedCategory)
                .map((category, catIndex) => (
                  <motion.section
                    key={category}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ delay: catIndex * 0.04 }}
                  >
                    <div className="mb-2 flex items-baseline gap-3">
                      <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">{categoryLabels[category]}</h2>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {groupedSources[category].length} source{groupedSources[category].length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="overflow-x-auto border-y border-[color:var(--g-border-default)]">
                      <table className="w-full min-w-[720px] text-left text-sm" data-testid="sources-table-view">
                        <thead className="border-b border-divide text-xs font-medium text-muted-foreground">
                          <tr>
                            <th className="py-2 pl-1 pr-3 font-medium">Source</th>
                            <th className="px-3 py-2 font-medium">Type</th>
                            <th className="px-3 py-2 font-medium">Status</th>
                            <th className="px-3 py-2 text-right font-medium">Tables</th>
                            <th className="px-3 py-2 text-right font-medium">Records</th>
                            <th className="px-3 py-2 text-right font-medium">Workflows</th>
                            <th className="px-3 py-2 font-medium">Last sync</th>
                          </tr>
                        </thead>
                        <tbody>
                          {groupedSources[category].map((source) => {
                            const selected = expandedSource === source.id
                            return (
                              <tr
                                key={source.id}
                                className={cn(
                                  "cursor-pointer border-b border-divide last:border-0",
                                  selected ? "bg-[color:var(--g-surface-active)]" : "hover:bg-[color:var(--g-surface-2)]",
                                )}
                                onClick={() => setExpandedSource(selected ? null : source.id)}
                              >
                                <td className="py-2.5 pl-1 pr-3 font-medium text-foreground">{source.name}</td>
                                <td className="px-3 py-2.5 text-muted-foreground">{source.type}</td>
                                <td className="px-3 py-2.5 capitalize text-foreground">
                                  <span className="inline-flex items-center gap-2">
                                    {source.status === "syncing" ? (
                                      <span
                                        className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--g-signal)] motion-safe:animate-pulse"
                                        data-source-ingest="syncing"
                                        aria-hidden
                                      />
                                    ) : (
                                      <span
                                        className={cn(
                                          "inline-block h-1.5 w-1.5 rounded-full",
                                          source.status === "connected" && "bg-[color:var(--g-brand)]",
                                          source.status === "error" && "bg-destructive",
                                          source.status === "disconnected" && "bg-muted-foreground/50",
                                        )}
                                        aria-hidden
                                      />
                                    )}
                                    {source.status}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{source.tables}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{source.records}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{source.workflowsUsing}</td>
                                <td className="px-3 py-2.5 text-muted-foreground">{source.lastSync}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    {groupedSources[category]
                      .filter((source) => source.id === expandedSource)
                      .map((source) => (
                        <div key={`${source.id}-inspect`} className="mt-3 max-w-xl">
                          <SourceTile
                            source={source}
                            index={0}
                            isExpanded
                            onToggle={() => setExpandedSource(null)}
                            onSync={handleSync}
                            onDelete={handleDelete}
                            isMutating={mutatingSourceId === source.id}
                          />
                        </div>
                      ))}
                  </motion.section>
                ))}
            </AnimatePresence>
          </div>

          <aside className="space-y-7 lg:border-l lg:border-[color:var(--g-border-default)] lg:pl-6" aria-label="Source operations">
            <section data-testid="sources-needs-attention">
              <h2 className="text-[13px] font-semibold text-foreground">Needs attention</h2>
              {sources.length === 0 ? (
                <p className="mt-2 text-[13px] text-muted-foreground">
                  {error ? "Source data unavailable." : "No sources connected yet."}
                </p>
              ) : needsAttention.length === 0 ? (
                <p className="mt-2 flex items-center gap-2 text-[13px] text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
                  No sources need attention.
                </p>
              ) : (
                <ul className="mt-2 divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
                  {needsAttention.map((source) => (
                    <li key={source.id}>
                      <button
                        type="button"
                        onClick={() => setExpandedSource(source.id)}
                        className="flex w-full items-center justify-between gap-3 py-2 text-left text-[13px] hover:text-foreground"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <span
                            className={cn(
                              "h-1.5 w-1.5 shrink-0 rounded-full",
                              source.status === "error" ? "bg-destructive" : "bg-muted-foreground/50",
                            )}
                            aria-hidden
                          />
                          <span className="truncate font-medium text-foreground">{source.name}</span>
                        </span>
                        <span className="shrink-0 text-xs capitalize text-muted-foreground">{source.status}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section data-testid="sources-recent-ingestion">
              <h2 className="text-[13px] font-semibold text-foreground">Recent ingestion</h2>
              {recentIngestion.length === 0 ? (
                <p className="mt-2 text-[13px] text-muted-foreground">
                  {error ? "Source data unavailable." : "No syncs recorded yet."}
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {recentIngestion.map((source) => (
                    <li key={source.id} className="flex items-baseline justify-between gap-3 text-[13px]">
                      <span className="truncate text-foreground">{source.name}</span>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {source.status === "syncing" ? "Syncing now" : source.lastSync}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="border-t border-[color:var(--g-border-default)] pt-5">
              <h2 className="text-[13px] font-semibold text-foreground">Connect a system</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                Databases and warehouses your agents and workflows can query.
              </p>
              <Button variant="outline" size="sm" className="mt-3 w-full" onClick={() => setAddModalOpen(true)} disabled={isLoading}>
                <Plus className="mr-1 h-4 w-4" />
                Add source
              </Button>
            </section>
          </aside>
        </div>
      </div>

      <AddDataSourceModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onCreate={handleCreate}
        creating={isCreatingSource}
      />
    </AppShell>
  )
}
