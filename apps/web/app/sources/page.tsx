"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Plus,
  RefreshCw,
} from "lucide-react"
import { ApiError, fetcher as apiFetcher, PlanRequiredApiError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { sourcesApi } from "@/lib/api"
import type { CreateSourceRequest } from "@/types/api"
import { AddDataSourceModal } from "@/components/gravitre/add-data-source-modal"
import { NoResultsState } from "@/components/gravitre/empty-state"
import { OperatingEmpty, PhaseBand } from "@/components/gravitre/operating/operating-primitives"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { toast } from "sonner"
import { useIsMobile } from "@/hooks/use-mobile"
import { SourceInspector, SourceInventoryRow } from "@/components/sources/source-inspector"
import { normalizeSourcesResponse, formatCompactCount, formatReportedCount, type Source } from "@/lib/source-inventory"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"

/** Data fabric stages: connection → ingestion → schema → available to agents as evidence. */
type FabricStage = "connected" | "ingesting" | "attention" | "schema" | "grounding"

const FABRIC_STAGE_MATCH: Record<FabricStage, (source: Source) => boolean> = {
  connected: (s) => s.status === "connected" || s.status === "syncing",
  ingesting: (s) => s.status === "syncing",
  attention: (s) => s.status === "error" || s.status === "disconnected",
  schema: (s) => (s.tables ?? 0) > 0,
  grounding: (s) => (s.workflowsUsing ?? 0) + (s.operatorsUsing ?? 0) > 0,
}

const categoryLabels = {
  sql: "SQL Databases",
  nosql: "NoSQL",
  warehouse: "Data Warehouses",
}

// Add Source Modal — see components/gravitre/add-data-source-modal.tsx

const SOURCES_TITLE = "Sources"
const SOURCES_DESCRIPTION = "Connected databases and warehouses your agents and workflows can query."

export default function SourcesPage() {
  const { user } = useAuth()
  const compactInspector = useIsMobile(1024)
  const reducedMotion = useReducedMotion()
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null)
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [mutatingSourceId, setMutatingSourceId] = useState<string | null>(null)
  const [isCreatingSource, setIsCreatingSource] = useState(false)
  const [fabricStage, setFabricStage] = useState<FabricStage | null>(null)
  const { data, error, isLoading, isValidating, mutate } = useSWR(user ? "/api/sources" : null, apiFetcher, {
    fallbackData: { sources: [] as Source[] },
    revalidateOnFocus: false,
    onSuccess: () => setLastFetchedAt(Date.now()),
    onError: (err) => console.error("[v0] Sources fetch error:", err),
  })
  const sources = normalizeSourcesResponse(data)
  const selectedSource = sources.find((source) => source.id === expandedSource) ?? null

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

  const stageSources = fabricStage ? sources.filter(FABRIC_STAGE_MATCH[fabricStage]) : sources
  const groupedSources = stageSources.reduce(
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
  const totalRecords = sources.reduce((acc, s) => acc + (s.recordCount ?? 0), 0)
  const totalTables = sources.reduce((a, s) => a + (s.tables ?? 0), 0)

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
      <div data-testid="sources-hub-b" data-composition="manage" className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          title={SOURCES_TITLE}
          description={SOURCES_DESCRIPTION}
          status={
            sources.length > 0 ? (
              <span className="flex flex-wrap items-center gap-x-4 gap-y-1" data-testid="sources-health-line">
                <LiveStatus tone={errorCount > 0 ? "attention" : connectedCount > 0 ? "live" : "idle"}>
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

        {sources.length > 0 ? (
          <PhaseBand
            label="Data fabric"
            active={fabricStage}
            onSelect={(next) => setFabricStage(next as FabricStage | null)}
            phases={[
              { id: "connected", label: "Connected", count: connectedCount, tone: "done", hint: `of ${sources.length} sources` },
              { id: "ingesting", label: "Ingesting now", count: sources.filter(FABRIC_STAGE_MATCH.ingesting).length, tone: "live" },
              { id: "attention", label: "Needs attention", count: needsAttention.length, tone: "risk" },
              { id: "schema", label: "Schema discovered", count: sources.filter(FABRIC_STAGE_MATCH.schema).length, tone: "neutral", hint: `${totalTables} tables` },
              { id: "grounding", label: "Grounding work", count: sources.filter(FABRIC_STAGE_MATCH.grounding).length, tone: "neutral", hint: "Used by workflows or agents" },
            ]}
          />
        ) : null}

        <div className="grid gap-8 px-[var(--np-page-pad-sm)] pb-8 pt-4 sm:px-[var(--np-page-pad)] lg:grid-cols-[minmax(0,1fr)_280px]">
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
                        "min-h-11 border-b-2 pb-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
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
                  updatedAt={lastFetchedAt}
                  isRefreshing={isValidating}
                  onRefresh={() => mutate()}
                />
              </div>
            </div>

            {isLoading && sources.length === 0 ? (
              <div className="h-40 animate-pulse rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)]" />
            ) : null}

            {!isLoading && !error && sources.length === 0 ? (
              <OperatingEmpty
                className="px-0 sm:px-0"
                title="No data sources yet"
                body="Sources are the business data your agents reason over. Once connected, Gravitre ingests it, discovers the schema and makes it available as evidence."
                path={["Connect a database or warehouse", "Ingest and sync", "Discover schema", "Ground agents with evidence"]}
                action={
                  <Button size="sm" onClick={() => setAddModalOpen(true)}>
                    <Plus className="mr-1 h-4 w-4" />
                    Add data source
                  </Button>
                }
              />
            ) : null}

            {!isLoading &&
            sources.length > 0 &&
            categories.filter((cat) => selectedCategory === null || cat === selectedCategory).length === 0 ? (
              <NoResultsState
                onClear={() => {
                  setSelectedCategory(null)
                  setFabricStage(null)
                }}
              />
            ) : null}

            <AnimatePresence mode="wait">
              {categories
                .filter((cat) => selectedCategory === null || cat === selectedCategory)
                .map((category, catIndex) => (
                  <motion.section
                    key={category}
                    initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
                    transition={{ delay: reducedMotion ? 0 : catIndex * 0.04, duration: reducedMotion ? 0 : 0.18 }}
                  >
                    <div className="mb-2 flex items-baseline gap-3">
                      <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">{categoryLabels[category]}</h2>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {groupedSources[category].length} source{groupedSources[category].length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="hidden overflow-x-auto lg:block border-y border-[color:var(--g-border-default)]">
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
                                <td className="py-2.5 pl-1 pr-3 font-medium text-foreground"><button type="button" aria-pressed={selected} onClick={(event) => { event.stopPropagation(); setExpandedSource(selected ? null : source.id) }} className="min-h-11 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{source.name}</button></td>
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
                                          (source.status === "disconnected" || source.status === "unknown") && "bg-muted-foreground/50",
                                        )}
                                        aria-hidden
                                      />
                                    )}
                                    {source.status === "unknown" ? "Status not reported" : source.status}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{formatReportedCount(source.tables)}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{source.records}</td>
                                <td className="px-3 py-2.5 text-right tabular-nums">{formatReportedCount(source.workflowsUsing)}</td>
                                <td className="px-3 py-2.5 text-muted-foreground">{source.lastSync}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="divide-y divide-[color:var(--g-border-subtle)] rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] lg:hidden" data-testid="sources-compact-view">
                      {groupedSources[category].map((source) => (
                        <SourceInventoryRow key={source.id} source={source} selected={expandedSource === source.id} onSelect={() => setExpandedSource(expandedSource === source.id ? null : source.id)} />
                      ))}
                    </div>
                  </motion.section>
                ))}
            </AnimatePresence>
          </div>

          <aside className="space-y-7 lg:border-l lg:border-[color:var(--g-border-default)] lg:pl-6" aria-label="Source operations">
            {selectedSource && !compactInspector ? (
              <SourceInspector source={selectedSource} onSync={handleSync} onDelete={handleDelete} isMutating={mutatingSourceId === selectedSource.id} />
            ) : null}
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
                        className="flex min-h-11 w-full items-center justify-between gap-3 py-2 text-left text-[13px] hover:text-foreground"
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

      <Sheet open={Boolean(selectedSource && compactInspector)} onOpenChange={(open) => { if (!open) setExpandedSource(null) }}>
        <SheetContent className="w-full overflow-y-auto pb-[env(safe-area-inset-bottom)] sm:max-w-[540px]">
          <SheetHeader className="pr-14">
            <SheetTitle className="font-[family-name:var(--font-space-grotesk)]">{selectedSource?.name ?? "Source"}</SheetTitle>
            <SheetDescription>Connection, schema and workflow context for the selected source.</SheetDescription>
          </SheetHeader>
          {selectedSource ? <div className="px-4 pb-6"><SourceInspector source={selectedSource} onSync={handleSync} onDelete={handleDelete} isMutating={mutatingSourceId === selectedSource.id} /></div> : null}
        </SheetContent>
      </Sheet>

      <AddDataSourceModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onCreate={handleCreate}
        creating={isCreatingSource}
      />
    </AppShell>
  )
}
