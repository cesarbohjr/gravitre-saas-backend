"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { Plus, RefreshCw, X } from "lucide-react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { hasConnectorBrandLogo } from "@/components/gravitre/connector-icon"
import { AddDataSourceModal } from "@/components/gravitre/add-data-source-modal"
import { SourceInspector, SourceInventoryRow } from "@/components/sources/source-inspector"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { ApiError, fetcher as apiFetcher, PlanRequiredApiError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { sourceSyncFeedback } from "@/lib/source-evidence"
import { sourcesApi } from "@/lib/api"
import { sourceTypeVendorKey } from "@/lib/brand-vendor"
import { useIsMobile } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"
import {
  formatCompactCount,
  formatRelativeSync,
  normalizeIngestionFeed,
  normalizeSourcesResponse,
  type Source,
  type SourceIngestionEvent,
} from "@/lib/source-inventory"
import type { CreateSourceRequest, SourceSyncHistoryItem } from "@/types/api"
import "@/components/workspace/ops-v4.css"

const SOURCES_TITLE = "Sources"

type TableFilter = "all" | "warehouse" | "errors"

const TABLE_FILTERS: Array<{ id: TableFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "warehouse", label: "Data warehouses" },
  { id: "errors", label: "Errors only" },
]

/** The six systems the design offers; ids are source catalog type ids. */
const CONNECT_TILES: Array<{ typeId: string; name: string; kind: string; mono: string }> = [
  { typeId: "snowflake", name: "Snowflake", kind: "Warehouse", mono: "SF" },
  { typeId: "bigquery", name: "BigQuery", kind: "Warehouse", mono: "BQ" },
  { typeId: "postgresql", name: "Postgres", kind: "Database", mono: "PG" },
  { typeId: "redshift", name: "Redshift", kind: "Warehouse", mono: "RS" },
  { typeId: "google_sheets", name: "Google Sheets", kind: "Spreadsheet", mono: "GS" },
  { typeId: "csv_upload", name: "File upload", kind: "CSV or Excel", mono: "CSV" },
]

const FILE_TYPES = new Set(["manual", "csv_upload", "csv", "parquet", "json_files", "jsonl", "file", "upload"])
const SIGN_IN_TYPES = new Set([
  "hubspot", "salesforce", "stripe", "notion", "airtable", "google_sheets", "zendesk", "jira", "github", "linear",
])

function needsAttention(source: Source): boolean {
  return source.status === "error" || source.status === "disconnected"
}

function isFileSource(source: Source): boolean {
  return FILE_TYPES.has(source.typeId) || FILE_TYPES.has(source.type.toLowerCase())
}

function usesSignIn(source: Source): boolean {
  return Boolean(source.connectorId) || SIGN_IN_TYPES.has(source.typeId)
}

/** Plain-language next step for a broken source; the raw error stays in the error log. */
function fixHint(source: Source): string {
  if (source.status === "disconnected") return "This source is disconnected. Reconnect it so agents can read from it again."
  if (isFileSource(source)) return "The uploaded file could not be read. Re-upload it or check the column headers."
  if (usesSignIn(source)) return "The last sync could not finish. Reconnecting usually refreshes an expired sign in."
  return "The last sync could not reach the database. Check the host, credentials and network access, then reconnect."
}

function monogram(name: string): string {
  const words = name.replace(/[^A-Za-z0-9 ]+/g, " ").trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

function updatedLabel(at: number | null, now: number): string {
  if (at == null) return "Not updated yet"
  const secs = Math.max(0, Math.floor((now - at) / 1000))
  if (secs < 45) return "Updated just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `Updated ${Math.max(1, mins)} min ago`
  return `Updated ${Math.floor(mins / 60)} h ago`
}

function statusLabel(source: Source): string {
  switch (source.status) {
    case "connected":
      return "Connected"
    case "syncing":
      return "Syncing"
    case "error":
      return "Error"
    case "disconnected":
      return "Disconnected"
    default:
      return "Not reported"
  }
}

function statusTone(source: Source): string | undefined {
  if (source.status === "error") return "red"
  if (source.status === "connected" || source.status === "syncing") return "green"
  if (source.status === "disconnected") return "amber"
  return undefined
}

/** Vendor mark in the design's monogram tile; falls back to initials when there is no official logo. */
function SourceMark({ source, small }: { source: Source; small?: boolean }) {
  const vendor = sourceTypeVendorKey(source.typeId || source.type)
  const branded = hasConnectorBrandLogo(vendor)
  return (
    <span className={cn("ov-mono", small && "sm", !branded && needsAttention(source) && usesSignIn(source) && "vendor")} aria-hidden>
      {branded ? <ProviderLogo provider={vendor} size="lg" decorative /> : monogram(source.name)}
    </span>
  )
}

function SyncBars({ source }: { source: Source }) {
  const points = source.recentSyncs.slice(-7)
  const pad = Math.max(0, 7 - points.length)
  const ok = points.filter((p) => p.status === "ok").length
  const failed = points.length - ok
  const label =
    points.length === 0
      ? "No sync reported in the last 7"
      : `Last ${points.length} sync${points.length === 1 ? "" : "s"}: ${ok} synced, ${failed} failed`
  return (
    <span className="ov-hist" role="img" aria-label={label}>
      {Array.from({ length: pad }, (_, i) => (
        <i key={`pad-${i}`} />
      ))}
      {points.map((point, i) => (
        <i
          key={`${point.createdAt ?? "p"}-${i}`}
          className={point.status === "ok" ? "ok" : "fail"}
          title={`${point.status === "ok" ? "Synced" : "Failed"}${point.createdAt ? ` · ${formatRelativeSync(point.createdAt)}` : ""}`}
        />
      ))}
    </span>
  )
}

function feedLine(event: SourceIngestionEvent, source: Source | undefined): { text: string; tone: "ok" | "fail" | "" } {
  const when = event.createdAt ? formatRelativeSync(event.createdAt) : "time not reported"
  if (event.kind === "created") {
    return { text: `${source && isFileSource(source) ? "Uploaded" : "Added"} · ${when}`, tone: "" }
  }
  if (event.kind === "updated") return { text: `Settings updated · ${when}`, tone: "" }
  if (event.status === "fail") return { text: `Sync failed · ${when}`, tone: "fail" }
  const records = event.records != null ? ` · ${formatCompactCount(event.records)} records` : ""
  return { text: `Synced${records} · ${when}`, tone: "ok" }
}

export default function SourcesPage() {
  const { user } = useAuth()
  const router = useRouter()
  const compactInspector = useIsMobile(1024)
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [expandedSource, setExpandedSource] = useState<string | null>(null)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [addTypeId, setAddTypeId] = useState<string | null>(null)
  const [tableFilter, setTableFilter] = useState<TableFilter>("all")
  const [mutatingSourceId, setMutatingSourceId] = useState<string | null>(null)
  const [isCreatingSource, setIsCreatingSource] = useState(false)
  const [errorLogFor, setErrorLogFor] = useState<Source | null>(null)
  const { data, error, isLoading, isValidating, mutate } = useSWR(user ? "/api/sources" : null, apiFetcher, {
    fallbackData: { sources: [] as Source[] },
    revalidateOnFocus: false,
    onSuccess: () => setLastFetchedAt(Date.now()),
  })
  const sources = useMemo(() => normalizeSourcesResponse(data), [data])
  const ingestion = useMemo(() => normalizeIngestionFeed(data), [data])
  const selectedSource = sources.find((source) => source.id === expandedSource) ?? null

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const { data: historyData, error: historyError, isLoading: historyLoading } = useSWR(
    errorLogFor ? ["source-sync-history", errorLogFor.id] : null,
    () => sourcesApi.getSyncHistory(errorLogFor!.id),
    { revalidateOnFocus: false },
  )

  const handleSync = async (sourceId: string) => {
    try {
      setMutatingSourceId(sourceId)
      const feedback = sourceSyncFeedback(await sourcesApi.sync(sourceId))
      if (feedback.kind === "error") toast.error(feedback.message)
      else if (feedback.kind === "success") toast.success(feedback.message)
      else toast.message(feedback.message)
      await mutate()
    } catch {
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
      if (expandedSource === sourceId) setExpandedSource(null)
    } catch {
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
      toast.error("Failed to create source")
      throw err
    } finally {
      setIsCreatingSource(false)
    }
  }

  /**
   * Sign-in sources go back through their connector; uploads go to the source page to re-upload.
   * Databases re-test the saved connection and sync when it answers.
   */
  const handleReconnect = async (source: Source) => {
    if (source.connectorId) {
      router.push(`/connectors/${encodeURIComponent(source.connectorId)}`)
      return
    }
    if (isFileSource(source)) {
      router.push(`/sources/${encodeURIComponent(source.id)}`)
      return
    }
    try {
      setMutatingSourceId(source.id)
      const result = await sourcesApi.testExisting(source.id)
      if (!result?.success) {
        toast.error(result?.message ? `Still cannot connect: ${result.message}` : "Still cannot connect. Check the connection details.", {
          action: { label: "Open source", onClick: () => router.push(`/sources/${encodeURIComponent(source.id)}`) },
        })
        return
      }
      const feedback = sourceSyncFeedback(await sourcesApi.sync(source.id))
      if (feedback.kind === "error") toast.error(feedback.message)
      else toast.success("Reconnected. Syncing now.")
      await mutate()
    } catch {
      toast.error("Reconnect failed")
    } finally {
      setMutatingSourceId((current) => (current === source.id ? null : current))
    }
  }

  const openAdd = (typeId: string | null) => {
    setAddTypeId(typeId)
    setAddModalOpen(true)
  }

  const attention = sources.filter(needsAttention)
  const connectedCount = sources.filter((s) => s.status === "connected" || s.status === "syncing").length
  const ingestingCount = sources.filter((s) => s.status === "syncing").length
  const tablesFound = sources.reduce((acc, s) => acc + (s.tables ?? 0), 0)
  const tableRows = sources.filter((s) =>
    tableFilter === "warehouse" ? s.category === "warehouse" : tableFilter === "errors" ? needsAttention(s) : true,
  )
  const filterCount = (id: TableFilter) =>
    id === "warehouse" ? sources.filter((s) => s.category === "warehouse").length : id === "errors" ? attention.length : sources.length
  const sourceById = new Map(sources.map((s) => [s.id, s]))
  const feed = ingestion.filter((event) => sourceById.has(event.sourceId)).slice(0, 8)
  // The shell's trial/plan strip already carries entitlement errors; repeating it inline is noise.
  const showInlineError =
    Boolean(error) && !(error instanceof PlanRequiredApiError) && !(error instanceof ApiError && error.status === 402)
  const loaded = !isLoading || sources.length > 0

  const select = (id: string) => setExpandedSource((current) => (current === id ? null : id))

  return (
    <AppShell title={SOURCES_TITLE}>
      <WsPage wide={false}>
        <div className="ov-page" data-testid="sources-hub-b" data-composition="manage">
          <section aria-labelledby="sources-hero" className="ov-hero">
            <div className="ov-hero-art">
              {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
              <img src="/illustrations/ops-sources.svg" alt="" />
            </div>
            <div className="ov-hero-copy">
              <div className="ov-hero-eb">
                <span className="ov-eyebrow">Data</span>
                {showInlineError ? (
                  <span className="ov-fresh stale" role="status">
                    <i aria-hidden />
                    Could not refresh
                  </span>
                ) : (
                  <span className="ov-fresh">
                    <i aria-hidden />
                    {isValidating && lastFetchedAt ? "Refreshing..." : updatedLabel(lastFetchedAt, now)}
                  </span>
                )}
              </div>
              <h1 id="sources-hero">Sources</h1>
              <p className="ov-lead">
                Connected databases and warehouses your agents and workflows can query. Fix what is broken first, then keep
                everything fresh.
              </p>
              <div className="ov-stats">
                <button
                  type="button"
                  className={cn("ov-stat", attention.length > 0 && "red")}
                  onClick={() => setTableFilter("errors")}
                >
                  <span className="v">{loaded ? attention.length : <span className="ov-skel-n" />}</span>
                  <span className="k">Need attention</span>
                </button>
                <button type="button" className="ov-stat" onClick={() => setTableFilter("all")}>
                  <span className="v">
                    {loaded ? connectedCount : <span className="ov-skel-n" />}
                    {loaded ? <small>of {sources.length}</small> : null}
                  </span>
                  <span className="k">Connected</span>
                </button>
                <div className={cn("ov-stat", ingestingCount > 0 && "green")}>
                  <span className="v">
                    {loaded ? ingestingCount : <span className="ov-skel-n" />}
                    {ingestingCount > 0 ? <i className="ov-live" aria-hidden /> : null}
                  </span>
                  <span className="k">Ingesting now</span>
                </div>
                <div className="ov-stat">
                  <span className="v">{loaded ? formatCompactCount(tablesFound) : <span className="ov-skel-n" />}</span>
                  <span className="k">Tables found</span>
                </div>
              </div>
              <div className="ov-actions">
                <button type="button" className="ov-btn dark" onClick={() => openAdd(null)} disabled={isLoading}>
                  <Plus size={16} aria-hidden />
                  Add source
                </button>
                <button type="button" className="ov-btn" onClick={() => void mutate()} disabled={isValidating}>
                  <RefreshCw size={16} aria-hidden className={cn(isValidating && "ov-spin")} />
                  Refresh
                </button>
              </div>
            </div>
          </section>

          {showInlineError ? (
            <div className="ov-alert" role="alert">
              <span>{error instanceof Error ? error.message : "Failed to load sources"}</span>
              <button type="button" className="ov-btn sm" onClick={() => void mutate()}>
                Retry
              </button>
            </div>
          ) : null}

          {attention.length > 0 ? (
            <section aria-labelledby="sources-fix-first" className="ov-panel" data-testid="sources-attention-first">
              <div className="ov-band red">
                <div className="ov-band-l">
                  <span className="ov-dots" aria-hidden>
                    <i />
                    <i />
                    <i />
                  </span>
                  <h2 id="sources-fix-first">Fix these first</h2>
                  <span className="note">Agents cannot read from these sources until they reconnect</span>
                </div>
              </div>
              <div className="ov-fixgrid">
                {attention.map((source) => (
                  <article key={source.id} className="ov-fixcard">
                    <div className="head">
                      <SourceMark source={source} />
                      <div className="who">
                        <b>{source.name}</b>
                        <span>
                          {source.typeId || source.type} · {source.status === "error" ? "failed" : "disconnected"}{" "}
                          {source.lastSyncAt ? source.lastSync.toLowerCase() : "at an unknown time"}
                        </span>
                      </div>
                      <span className={cn("ov-status", statusTone(source))}>
                        <i aria-hidden />
                        {statusLabel(source)}
                      </span>
                    </div>
                    <p>{fixHint(source)}</p>
                    <div className="acts">
                      <button
                        type="button"
                        className="ov-btn dark sm"
                        disabled={mutatingSourceId === source.id}
                        onClick={() => void handleReconnect(source)}
                      >
                        {mutatingSourceId === source.id ? "Reconnecting..." : "Reconnect"}
                      </button>
                      <button type="button" className="ov-btn sm" onClick={() => setErrorLogFor(source)}>
                        View error log
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <div className="ov-row2">
            <section aria-labelledby="sources-all" className="ov-panel ov-grow">
              <div className="ov-band">
                <div className="ov-band-l">
                  <span className="ov-dots" aria-hidden>
                    <i />
                    <i />
                    <i />
                  </span>
                  <h2 id="sources-all">
                    All sources <span className="n">{sources.length}</span>
                  </h2>
                </div>
                <div className="ov-seg" role="group" aria-label="Filter sources">
                  {TABLE_FILTERS.map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      aria-pressed={tableFilter === f.id}
                      onClick={() => setTableFilter(f.id)}
                      title={`${filterCount(f.id)} source${filterCount(f.id) === 1 ? "" : "s"}`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              {isLoading && sources.length === 0 ? (
                <div className="ov-empty" aria-busy="true">
                  <p>Loading sources...</p>
                </div>
              ) : !error && sources.length === 0 ? (
                <div className="ov-empty">
                  <b>No data sources yet</b>
                  <p>
                    Sources are the business data your agents reason over. Once connected, Gravitre ingests it, discovers the
                    schema and makes it available as evidence.
                  </p>
                  <button type="button" className="ov-btn dark sm" onClick={() => openAdd(null)}>
                    <Plus size={14} aria-hidden />
                    Add data source
                  </button>
                </div>
              ) : tableRows.length === 0 && sources.length > 0 ? (
                <div className="ov-empty">
                  <b>{tableFilter === "errors" ? "Nothing is broken" : "No data warehouses connected"}</b>
                  <button type="button" className="ov-linkbtn" onClick={() => setTableFilter("all")}>
                    Show all sources
                  </button>
                </div>
              ) : (
                <>
                  <div className="ov-table-wrap ov-only-wide">
                    <table className="ov-table" data-testid="sources-table-view">
                      <thead>
                        <tr className="ov-tr th">
                          <th scope="col">Source</th>
                          <th scope="col">Status</th>
                          <th scope="col">Last 7 syncs</th>
                          <th scope="col">Records</th>
                          <th scope="col">Last sync</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tableRows.map((source) => {
                          const selected = expandedSource === source.id
                          return (
                            <tr
                              key={source.id}
                              className="ov-tr row"
                              aria-selected={selected}
                              onClick={() => select(source.id)}
                            >
                              <td>
                                <button
                                  type="button"
                                  className="ov-src"
                                  aria-pressed={selected}
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    select(source.id)
                                  }}
                                >
                                  <SourceMark source={source} small />
                                  <span className="nm">
                                    <b>{source.name}</b>
                                    <span>{source.typeId || source.type}</span>
                                  </span>
                                </button>
                              </td>
                              <td>
                                <span className={cn("ov-status", statusTone(source))}>
                                  {source.status === "syncing" ? (
                                    <i className="ov-pulse" data-source-ingest="syncing" aria-hidden />
                                  ) : (
                                    <i aria-hidden />
                                  )}
                                  {statusLabel(source)}
                                </span>
                              </td>
                              <td>
                                <SyncBars source={source} />
                              </td>
                              <td className="ov-cell">{source.recordCount == null ? "Not reported" : formatCompactCount(source.recordCount)}</td>
                              <td className="ov-cell m">{source.lastSync}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="ov-only-narrow ov-compact" data-testid="sources-compact-view">
                    {tableRows.map((source) => (
                      <SourceInventoryRow
                        key={source.id}
                        source={source}
                        selected={expandedSource === source.id}
                        onSelect={() => select(source.id)}
                      />
                    ))}
                  </div>
                  <div className="ov-legend" aria-hidden>
                    <span>
                      <i className="ok" />
                      Synced
                    </span>
                    <span>
                      <i className="fail" />
                      Failed
                    </span>
                    <span>
                      <i />
                      No report
                    </span>
                  </div>
                </>
              )}
            </section>

            <aside className="ov-side" aria-label="Source operations">
              {selectedSource && !compactInspector ? (
                <section className="ov-panel" aria-labelledby="sources-selected">
                  <div className="ov-band">
                    <div className="ov-band-l">
                      <h2 id="sources-selected">{selectedSource.name}</h2>
                    </div>
                    <button
                      type="button"
                      className="ov-linkbtn"
                      aria-label="Close source details"
                      onClick={() => setExpandedSource(null)}
                    >
                      <X size={16} aria-hidden />
                    </button>
                  </div>
                  <div className="ov-side-body">
                    <SourceInspector
                      source={selectedSource}
                      onSync={handleSync}
                      onDelete={handleDelete}
                      isMutating={mutatingSourceId === selectedSource.id}
                    />
                  </div>
                </section>
              ) : null}
              <section className="ov-panel" aria-labelledby="sources-ingestion" data-testid="sources-recent-ingestion">
                <div className="ov-band">
                  <div className="ov-band-l">
                    <span className="ov-dots" aria-hidden>
                      <i />
                      <i />
                      <i />
                    </span>
                    <h2 id="sources-ingestion">Recent ingestion</h2>
                  </div>
                </div>
                {feed.length === 0 ? (
                  <p className="ov-side-empty">{error ? "Source data unavailable." : "No syncs recorded yet."}</p>
                ) : (
                  <ul className="ov-feed">
                    {feed.map((event, index) => {
                      const source = sourceById.get(event.sourceId)
                      const line = feedLine(event, source)
                      return (
                        <li key={`${event.sourceId}-${event.createdAt ?? index}-${index}`}>
                          <span className="rail" aria-hidden>
                            <i className={line.tone} />
                            {index < feed.length - 1 ? <span /> : null}
                          </span>
                          <span className="txt">
                            <button type="button" className="ov-feed-name" onClick={() => setExpandedSource(event.sourceId)}>
                              {source?.name ?? "Source"}
                            </button>
                            <span>{line.text}</span>
                          </span>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </section>
            </aside>
          </div>

          <section aria-labelledby="sources-connect" className="ov-explain">
            <div className="ov-explain-side">
              <div className="ov-sq-row">
                <span className="ov-sq slate" aria-hidden />
                <h2 id="sources-connect">Connect a system</h2>
              </div>
              <p>Give agents grounded answers by connecting the place your numbers already live. Read only by default.</p>
              <Link href="/connectors">Browse every connector</Link>
            </div>
            <div className="ov-tiles">
              {CONNECT_TILES.map((tile) => {
                const vendor = sourceTypeVendorKey(tile.typeId)
                const branded = hasConnectorBrandLogo(vendor)
                return (
                  <button
                    key={tile.typeId}
                    type="button"
                    className="ov-tile"
                    onClick={() => openAdd(tile.typeId)}
                    aria-label={`Connect ${tile.name}`}
                  >
                    <span className="ov-mono" aria-hidden>
                      {branded ? <ProviderLogo provider={vendor} size="lg" decorative /> : tile.mono}
                    </span>
                    <span>
                      <b>{tile.name}</b>
                      <br />
                      <span className="k">{tile.kind}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </section>
        </div>
      </WsPage>

      <Sheet open={Boolean(selectedSource && compactInspector)} onOpenChange={(open) => { if (!open) setExpandedSource(null) }}>
        <SheetContent className="w-full overflow-y-auto pb-[env(safe-area-inset-bottom)] sm:max-w-[540px]">
          <SheetHeader className="pr-14">
            <SheetTitle className="font-sans">{selectedSource?.name ?? "Source"}</SheetTitle>
            <SheetDescription>Connection, schema and workflow context for the selected source.</SheetDescription>
          </SheetHeader>
          {selectedSource ? (
            <div className="px-4 pb-6">
              <SourceInspector source={selectedSource} onSync={handleSync} onDelete={handleDelete} isMutating={mutatingSourceId === selectedSource.id} />
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <Sheet open={Boolean(errorLogFor)} onOpenChange={(open) => { if (!open) setErrorLogFor(null) }}>
        <SheetContent className="w-full overflow-y-auto pb-[env(safe-area-inset-bottom)] sm:max-w-[540px]">
          <SheetHeader className="pr-14">
            <SheetTitle className="font-sans">Error log · {errorLogFor?.name ?? "Source"}</SheetTitle>
            <SheetDescription>Every sync and connection change recorded for this source, newest first.</SheetDescription>
          </SheetHeader>
          <div className="space-y-3 px-4 pb-6 text-sm">
            {errorLogFor?.lastSyncError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/[0.04] p-3">
                <p className="text-xs font-medium text-muted-foreground">Last error</p>
                <p className="mt-1 break-words font-mono text-xs text-foreground">{errorLogFor.lastSyncError}</p>
              </div>
            ) : null}
            {historyLoading ? <p className="text-muted-foreground">Loading history...</p> : null}
            {historyError ? <p className="text-destructive">Could not load the sync history.</p> : null}
            {!historyLoading && !historyError && (historyData?.history ?? []).length === 0 ? (
              <p className="text-muted-foreground">No syncs recorded for this source yet.</p>
            ) : null}
            <ul className="divide-y divide-[color:var(--g-border-subtle)]">
              {(historyData?.history ?? []).map((item: SourceSyncHistoryItem) => (
                <li key={item.id} className="py-2">
                  <p className="flex items-center justify-between gap-3">
                    <span className="font-medium text-foreground">
                      {item.status === "error" || item.status === "failed" ? "Sync failed" : item.action === "source.created" ? "Added" : "Synced"}
                    </span>
                    <span className="text-xs text-muted-foreground">{item.createdAt ? formatRelativeSync(item.createdAt) : ""}</span>
                  </p>
                  {item.error ? <p className="mt-1 break-words font-mono text-xs text-destructive">{item.error}</p> : null}
                  {item.records != null ? <p className="mt-1 text-xs text-muted-foreground">{formatCompactCount(item.records)} records</p> : null}
                </li>
              ))}
            </ul>
            {errorLogFor ? (
              <Link className="inline-block text-sm font-medium underline" href={`/sources/${encodeURIComponent(errorLogFor.id)}`}>
                Open source details
              </Link>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>

      <AddDataSourceModal
        open={addModalOpen}
        onClose={() => {
          setAddModalOpen(false)
          setAddTypeId(null)
        }}
        onCreate={handleCreate}
        creating={isCreatingSource}
        initialTypeId={addTypeId}
      />
    </AppShell>
  )
}
