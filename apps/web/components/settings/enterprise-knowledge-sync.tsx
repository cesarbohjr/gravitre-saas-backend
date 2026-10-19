"use client"

/**
 * Enterprise > Knowledge sync (design p18): tiles, 14 day ingest chart and the
 * sources table from GET /api/enterprise/insights/knowledge-sync. Sync now and
 * Retry call the real trigger (POST /api/knowledge/connectors/{id}/sync), which
 * runs the sync before it answers, so the row shows Syncing until it returns.
 * DISABLE_INGESTION and the lifecycle hold are shown as they are and turn the
 * sync buttons off.
 */
import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { BookOpen, CalendarClock, FileText, OctagonAlert, RefreshCw, TriangleAlert } from "lucide-react"
import { knowledgeSyncApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import {
  KNOWLEDGE_SYNC_KEY,
  ingestBars,
  sourceStatusMeta,
  type KnowledgeSource,
  type KnowledgeSyncOverview,
} from "@/lib/settings-api/enterprise"
import { SetError, SetNote, SetPill, SetSkeleton, SetSwitch, formatAgo, formatMoment } from "./settings-kit"

function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`)
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" })
}

export function EnterpriseKnowledgeSync({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<KnowledgeSyncOverview>(KNOWLEDGE_SYNC_KEY, fetcher, {
    revalidateOnFocus: false,
  })
  const jobs = useSWR("knowledge-sync-jobs", () => knowledgeSyncApi.listSyncJobs({ limit: 25 }), {
    revalidateOnFocus: false,
  })
  const [syncing, setSyncing] = useState<Record<string, boolean>>({})
  const [fullSync, setFullSync] = useState(false)
  const [announce, setAnnounce] = useState("")

  const blocked = Boolean(data?.ingestionDisabled || data?.heldReason)
  const canSync = isAdmin && !blocked

  const runSync = async (source: KnowledgeSource): Promise<boolean> => {
    setSyncing((s) => ({ ...s, [source.connectorId]: true }))
    setAnnounce(`Syncing ${source.name}`)
    try {
      await knowledgeSyncApi.triggerConnectorSync(source.connectorId, { fullSync: isAdmin && fullSync })
      setAnnounce(`${source.name} synced`)
      return true
    } catch (err) {
      toast.error(`${source.name}: ${err instanceof Error ? err.message : "sync failed"}`)
      setAnnounce(`${source.name} sync failed`)
      return false
    } finally {
      setSyncing((s) => {
        const next = { ...s }
        delete next[source.connectorId]
        return next
      })
    }
  }

  const syncOne = async (source: KnowledgeSource) => {
    if (!canSync) return
    const ok = await runSync(source)
    if (ok) toast.success(`${source.name} synced`)
    await Promise.all([mutate(), jobs.mutate()])
  }

  const syncable = (data?.sources ?? []).filter((s) => {
    const meta = sourceStatusMeta(s.status)
    return (meta.cta === "Sync now" || meta.cta === "Retry") && !s.heldReason
  })

  const syncAll = async () => {
    if (!canSync || syncable.length === 0) return
    let ok = 0
    for (const source of syncable) {
      if (await runSync(source)) ok += 1
    }
    toast.success(`Synced ${ok} of ${syncable.length} sources`)
    await Promise.all([mutate(), jobs.mutate()])
  }

  const anyRunning = Object.keys(syncing).length > 0
  const bars = ingestBars(data?.days ?? [])

  return (
    <>
      <div className="ent-intro">
        <p>Keeps Gravitre&apos;s knowledge in step with your connectors.</p>
        <div className="ent-actions">
          {isAdmin ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--gs-ink-3)" }}>
              <SetSwitch checked={fullSync} onChange={setFullSync} label="Full sync, re-ingest everything" disabled={!canSync} />
              Full sync
            </span>
          ) : null}
          <button
            type="button"
            className="gs-btn dark sm"
            disabled={!canSync || anyRunning || syncable.length === 0}
            onClick={() => void syncAll()}
          >
            <RefreshCw size={15} className={anyRunning ? "animate-spin" : undefined} aria-hidden />
            Sync all now
          </button>
        </div>
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        {announce}
      </span>

      {data?.ingestionDisabled ? (
        <SetNote tone="amber" icon={OctagonAlert}>
          Ingestion is turned off for this deployment (DISABLE_INGESTION), so no source can sync right now. Scheduled syncs
          are skipped and nothing is written until it is turned back on.
        </SetNote>
      ) : data?.heldReason ? (
        <SetNote tone="amber" icon={TriangleAlert}>
          Syncs are on hold until data lifecycle checks pass ({data.heldReason}).
        </SetNote>
      ) : null}

      {error && !data ? (
        <section className="gs-card">
          <SetError message="Knowledge sync did not load." onRetry={() => void mutate()} />
        </section>
      ) : isLoading || !data ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading knowledge sync" />
        </section>
      ) : (
        <>
          <div className="gs-minis">
            <div className="gs-mini">
              <div className="l">Sources syncing</div>
              <div className="v">{data.sourcesSyncing}</div>
              <div className="d">of {data.sourceCount} connected</div>
            </div>
            <div className="gs-mini">
              <div className="l">Documents indexed</div>
              <div className="v">{data.documentsIndexed == null ? "None yet" : data.documentsIndexed.toLocaleString()}</div>
            </div>
            <div className="gs-mini">
              <div className="l">Last sync</div>
              <div className="v">{formatAgo(data.lastSyncAt) ?? "None yet"}</div>
            </div>
            <div className={`gs-mini${data.failedJobs > 0 ? " ent-tile-red" : ""}`}>
              <div className="l">Failed jobs</div>
              <div className="v">{data.failedJobs}</div>
              <div className="d">last {data.windowDays} days</div>
            </div>
          </div>

          <section className="gs-card ent-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <h3>Documents ingested, last {data.windowDays} days</h3>
              <span className="gs-count">{data.totalDocuments.toLocaleString()} total</span>
            </div>
            <div className="ent-bars" role="img" aria-label={`Daily ingest volume, ${data.totalDocuments} documents in ${data.windowDays} days`}>
              {bars.map((bar, i) => (
                <span
                  key={bar.date}
                  className={bar.zero ? "zero" : undefined}
                  title={`${dayLabel(bar.date)}: ${bar.documents} docs`}
                  style={{ height: `${bar.heightPct}%`, animationDelay: `${i * 40}ms` }}
                />
              ))}
            </div>
            {bars.length > 0 ? (
              <div className="ent-axis gs-mono">
                <span>{dayLabel(bars[0].date)}</span>
                <span>{dayLabel(bars[bars.length - 1].date)}</span>
              </div>
            ) : null}
          </section>

          <section className="gs-card clip">
            {data.sources.length === 0 ? (
              <div className="gs-empty">
                <BookOpen size={22} aria-hidden />
                <b>No knowledge sources yet</b>
                <p>Connect Notion, Confluence, HubSpot or Zendesk to keep their documents in Gravitre&apos;s knowledge.</p>
                <Link className="gs-btn line sm" href="/connectors">
                  Open connectors
                </Link>
              </div>
            ) : (
              <div className="gs-scroll-x">
                <div className="gs-tbl stack" style={{ ["--cols" as string]: "minmax(160px,1fr) 130px 90px 130px 110px", minWidth: 0 }}>
                  <div className="gs-tr head" style={{ background: "var(--gs-band)" }}>
                    <div className="gs-th">Source</div>
                    <div className="gs-th">Status</div>
                    <div className="gs-th">Docs</div>
                    <div className="gs-th">Last sync</div>
                    <div className="gs-th">
                      <span className="sr-only">Action</span>
                    </div>
                  </div>
                  {data.sources.map((source) => {
                    const running = Boolean(syncing[source.connectorId])
                    const meta = sourceStatusMeta(running ? "syncing" : source.status)
                    return (
                      <div key={source.connectorId} className="gs-row">
                        <div className="gs-td">
                          <div className="t">{source.name}</div>
                          <div className="s">
                            {source.syncConfigured ? source.schedule : "No sync targets set"}
                            {source.lastError ? ` · ${source.lastError}` : ""}
                          </div>
                        </div>
                        <div className="gs-td">
                          <SetPill tone={meta.tone} dot live={running || source.status === "syncing"}>
                            {meta.label}
                          </SetPill>
                        </div>
                        <div className="gs-td gs-mono" style={{ fontSize: 13 }} title="Documents synced in the last 14 days">
                          {source.docs14d.toLocaleString()}
                        </div>
                        <div className="gs-td" style={{ fontSize: 13, color: "var(--gs-ink-3)" }}>
                          {running ? "Running now" : formatAgo(source.lastSyncAt) ?? "Never"}
                        </div>
                        <div className="gs-td">
                          {running || source.status === "syncing" ? (
                            <span className="gs-btn text sm" aria-disabled>
                              Syncing
                            </span>
                          ) : meta.cta === "Resume" ? (
                            <Link className="gs-btn text sm" href={`/connectors?id=${encodeURIComponent(source.connectorId)}`}>
                              Resume
                            </Link>
                          ) : meta.cta ? (
                            <button
                              type="button"
                              className="gs-btn text sm"
                              disabled={!canSync || anyRunning || Boolean(source.heldReason)}
                              onClick={() => void syncOne(source)}
                            >
                              {meta.cta}
                            </button>
                          ) : source.status === "not_configured" ? (
                            <Link className="gs-btn text sm" href={`/connectors?id=${encodeURIComponent(source.connectorId)}`}>
                              Set up
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            <div className="gs-foot">
              <span>Docs counts pages synced in the last {data.windowDays} days. Scheduled syncs run on each source&apos;s schedule.</span>
            </div>
          </section>
        </>
      )}

      <section className="gs-card">
        <details>
          <summary className="gs-card-head" style={{ cursor: "pointer", borderBottom: 0 }}>
            <h3 style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
              <CalendarClock size={16} aria-hidden />
              Recent sync jobs
            </h3>
          </summary>
          {jobs.error && !jobs.data ? (
            <SetError message="Sync jobs did not load." onRetry={() => void jobs.mutate()} />
          ) : !jobs.data ? (
            <SetSkeleton rows={2} />
          ) : jobs.data.jobs.length === 0 ? (
            <p className="gs-sub" style={{ padding: "0 20px 16px" }}>
              None yet
            </p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {jobs.data.jobs.map((job) => {
                const name = data?.sources.find((s) => s.connectorId === job.connector_id)?.name ?? job.source_type
                return (
                  <li key={job.id} className="gs-row-sec">
                    <FileText size={16} aria-hidden style={{ color: "var(--gs-faint)" }} />
                    <div className="gs-what">
                      <b>
                        {name} · {job.status}
                      </b>
                      <span>
                        {job.trigger_type} · {formatMoment(job.created_at) ?? ""}
                        {job.pages_synced != null ? ` · ${job.pages_synced} pages` : ""}
                        {job.error_message ? ` · ${job.error_message}` : ""}
                      </span>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </details>
      </section>
    </>
  )
}

