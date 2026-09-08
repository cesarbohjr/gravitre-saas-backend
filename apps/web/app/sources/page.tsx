"use client"

import { useState } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
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
import { NucleoConnector } from "@/components/icons/nucleo/semantic"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { sourcesApi } from "@/lib/api"
import { buildWorkflowFromSourceUrl } from "@/lib/source-workflow-handoff"
import type { CreateSourceRequest } from "@/types/api"
import { AddDataSourceModal } from "@/components/gravitre/add-data-source-modal"
import { EmptyState, NoResultsState } from "@/components/gravitre/empty-state"
import { CardSkeleton } from "@/components/gravitre/loading-state"
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
    lastSync: formatRelativeSync(
      (input.lastSync as string | null) ??
        (input.last_sync as string | null) ??
        (input.lastSyncAt as string | null)
    ),
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
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, type: "spring", stiffness: 100 }}
      whileHover={{ y: -2 }}
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
              "rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide",
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
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Table2 className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.tables}</p>
            <p className="text-[9px] text-muted-foreground">tables</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Database className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.records}</p>
            <p className="text-[9px] text-muted-foreground">records</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Workflow className="h-3 w-3" />
            </div>
            <p className="text-sm font-semibold text-foreground">{source.workflowsUsing}</p>
            <p className="text-[9px] text-muted-foreground">workflows</p>
          </div>
        </div>

        {/* Table preview */}
        {source.topTables && (
          <div className="mb-3">
            <div className="flex items-center gap-1 flex-wrap">
              {source.topTables.slice(0, 3).map((table) => (
                <span 
                  key={table}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground"
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
                  className="h-7 gap-1.5 text-xs text-red-400 border-red-500/30 hover:bg-red-500/10"
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

  return (
    <AppShell title={SOURCES_TITLE}>
      <div>
        <GravitrePageHeader
          title={SOURCES_TITLE}
          description={SOURCES_DESCRIPTION}
          icon={<NucleoConnector className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("mr-1 h-4 w-4", isValidating && "animate-spin")} />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setAddModalOpen(true)} disabled={isLoading}>
                <Plus className="mr-1 h-4 w-4" />
                Add Source
              </Button>
            </div>
          }
        />

        <div className="space-y-6 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          {error ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              <span>{error instanceof Error ? error.message : "Failed to load sources"}</span>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => mutate()}>
                Retry
              </Button>
            </div>
          ) : null}

          <section className="grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4">
            <GravitreMetric label="Connected" value={connectedCount} hint="Connected or syncing" />
            <GravitreMetric
              label="Records"
              value={formatCompactCount(totalRecords)}
              hint="Across listed sources"
            />
            <GravitreMetric label="Tables" value={totalTables} hint="Schema table count" />
            <GravitreMetric
              label="Errors"
              value={errorCount}
              hint="Sources needing attention"
              warning={errorCount > 0}
            />
          </section>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                  selectedCategory === null
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground",
                )}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                    selectedCategory === cat
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-muted-foreground hover:text-foreground",
                  )}
                >
                  {categoryLabels[cat]}
                </button>
              ))}
            </div>
            <DataFreshness
              updatedAt={data ? Date.now() : null}
              isRefreshing={isValidating}
              onRefresh={() => mutate()}
            />
          </div>

          {isLoading && sources.length === 0 ? (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : null}

          {!isLoading && !error && sources.length === 0 ? (
            <EmptyState
              icon={Database}
              title="No data sources yet"
              description="Connect your first data source to ground your agents in real business data."
              action={{ label: "Add Data Source", onClick: () => setAddModalOpen(true) }}
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
                <motion.div
                  key={category}
                  className="mb-10"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ delay: catIndex * 0.05 }}
                >
                  <div className="mb-4 flex items-center gap-3">
                    <h2 className="text-base font-semibold text-foreground">{categoryLabels[category]}</h2>
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground">
                      {groupedSources[category].length} source
                      {groupedSources[category].length !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {groupedSources[category].map((source, index) => (
                      <SourceTile
                        key={source.id}
                        source={source}
                        index={index}
                        isExpanded={expandedSource === source.id}
                        onToggle={() =>
                          setExpandedSource(expandedSource === source.id ? null : source.id)
                        }
                        onSync={handleSync}
                        onDelete={handleDelete}
                        isMutating={mutatingSourceId === source.id}
                      />
                    ))}
                  </div>
                </motion.div>
              ))}
          </AnimatePresence>
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
