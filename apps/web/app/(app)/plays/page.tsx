"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { ArrowRight, LayoutGrid, Rows3, Search, SquareKanban } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { AuPages, paginate } from "@/components/workspace/au-pages"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { apiFetch, fetcher } from "@/lib/fetcher"
import { playsApi, type PlayImpactSummary, type PlayListItem, type PlayOperatingMode } from "@/lib/api"
import { resolveProvider } from "@/lib/provider-registry"
import { cn } from "@/lib/utils"
import {
  READINESS_LABEL,
  TIER_LABEL,
  TIER_ORDER,
  connectorChips,
  departmentArt,
  departmentKey,
  departmentLabel,
  filterPlays,
  installationBody,
  ladder,
  nextGrant,
  readinessOf,
  setupHref,
  shareOf,
  summarize,
  tierOf,
  type PlayFilters,
  type PlayReadinessState,
  type PlayTier,
} from "@/components/plays/plays-board-model"
import "@/components/workspace/ops-v4.css"
import "@/components/workspace/automate-v1.css"

type PlaysResponse = { plays: PlayListItem[]; count: number }
type View = "cards" | "board" | "table"

const PAGE_SIZE = 10

const VIEWS: Array<{ id: View; label: string; icon: typeof LayoutGrid }> = [
  { id: "cards", label: "Cards", icon: LayoutGrid },
  { id: "board", label: "Authority board", icon: SquareKanban },
  { id: "table", label: "Table", icon: Rows3 },
]

/** The three authority levels, each with its library scene. */
const TIERS: Array<{ tier: Exclude<PlayTier, "off">; n: string; title: string; body: string; art: string; alt: string }> = [
  {
    tier: "observe",
    n: "01",
    title: "Watch and report",
    body: "The play reads your data and tells you what it would do. Nothing changes in your apps.",
    art: "/illustrations/ops-activity.svg",
    alt: "",
  },
  {
    tier: "recommend",
    n: "02",
    title: "Suggest, you decide",
    body: "Each move arrives as a recommendation. You approve, edit or skip it.",
    art: "/illustrations/ops-approvals.svg",
    alt: "",
  },
  {
    tier: "act",
    n: "03",
    title: "Act with approval",
    body: "The play prepares changes in your apps and each one waits for a person to approve it.",
    art: "/illustrations/agents-guardrails.svg",
    alt: "",
  },
]

const EMPTY_FILTERS: PlayFilters = { query: "", department: "all", readiness: "all", tier: "all" }

function vendorName(slug: string): string {
  return resolveProvider(slug)?.name ?? slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function workflowsLabel(count: number): string {
  return count === 1 ? "1 workflow" : `${count} workflows`
}

function ReadinessBadge({ state }: { state: PlayReadinessState }) {
  return (
    <span className={cn("au-ready", state === "connector" && "warn", state === "setup" && "muted")}>
      <i aria-hidden />
      {READINESS_LABEL[state]}
    </span>
  )
}

function TierChip({ tier }: { tier: PlayTier }) {
  return (
    <span className={cn("au-tier", `tone-${tier}`)}>
      <i aria-hidden />
      {TIER_LABEL[tier]}
    </span>
  )
}

export default function PlaysPage() {
  return (
    <AppShell title="Plays">
      <WsPage wide={false}>
        <PlaysBoard />
      </WsPage>
    </AppShell>
  )
}

function PlaysBoard() {
  const { data, error, isLoading, isValidating, mutate } = useSWR<PlaysResponse>("/api/plays", fetcher, {
    refreshInterval: 30_000,
  })
  const { data: impact, mutate: mutateImpact } = useSWR<PlayImpactSummary>("/api/plays/impact", () => playsApi.impact(), {
    revalidateOnFocus: true,
    refreshInterval: 60_000,
  })
  const plays = useMemo(() => data?.plays ?? [], [data])
  const summary = useMemo(() => summarize(plays), [plays])

  const [filters, setFilters] = useState<PlayFilters>(EMPTY_FILTERS)
  const [view, setView] = useState<View>("cards")
  const [page, setPage] = useState(1)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [grantTarget, setGrantTarget] = useState<{ item: PlayListItem; mode: PlayOperatingMode; label: string } | null>(null)
  const [granting, setGranting] = useState(false)

  const setFilter = <K extends keyof PlayFilters>(key: K, value: PlayFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }

  const departments = useMemo(() => {
    const keys = Array.from(new Set(plays.map(departmentKey)))
    return keys.sort((a, b) => departmentLabel(a).localeCompare(departmentLabel(b)))
  }, [plays])

  const visible = useMemo(() => filterPlays(plays, filters), [plays, filters])
  const paged = paginate(visible, page, PAGE_SIZE)
  const selected = visible.find((item) => item.play.key === selectedKey) ?? paged.rows[0] ?? null

  // Only a play the user picked becomes AI context; the default first card does not.
  const picked = selectedKey ? visible.find((item) => item.play.key === selectedKey) ?? null : null
  usePublishGravitreAISelection(picked ? { kind: "play", id: picked.play.key, label: picked.play.name } : null)

  useEffect(() => {
    if (paged.page !== page) setPage(paged.page)
  }, [paged.page, page])

  const verifiedByPlay = useMemo(() => {
    const map = new Map<string, number>()
    for (const row of impact?.plays ?? []) map.set(row.playKey, row.verifiedSuccessCount)
    return map
  }, [impact])

  const tierCounts: Array<{ id: "all" | PlayTier; label: string; count: number; dot: string }> = [
    { id: "all", label: "All", count: summary.total, dot: "ink" },
    { id: "observe", label: "Observe", count: summary.tiers.observe, dot: "" },
    { id: "recommend", label: "Recommend", count: summary.tiers.recommend, dot: "amber" },
    { id: "act", label: "Act", count: summary.tiers.act, dot: "green" },
    { id: "off", label: "Not on", count: summary.tiers.off, dot: "" },
  ]

  const showReady = filters.readiness === "ready" && filters.tier === "all"

  const grant = async () => {
    if (!grantTarget) return
    const { item, mode, label } = grantTarget
    setGranting(true)
    try {
      const response = await apiFetch(`/api/plays/${encodeURIComponent(item.play.key)}/installation`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(installationBody(item, mode, item.installation)),
      })
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null
        throw new Error(typeof payload?.detail === "string" ? payload.detail : "Could not change this play's authority.")
      }
      toast.success(`${item.play.name}: ${label.replace(/^Grant |^Turn on /, "")} is on`)
      setGrantTarget(null)
      await Promise.all([mutate(), mutateImpact()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not change this play's authority.")
    } finally {
      setGranting(false)
    }
  }

  const loading = isLoading && !data

  return (
    <div className="ov-page" data-composition="operate">
      <section aria-labelledby="plays-hero" className="ov-hero">
        <div className="ov-hero-art">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
          <img src="/illustrations/hero-plays.svg" alt="" />
          {plays.length ? (
            <div className="au-art-chip">
              <span className="t">
                <i aria-hidden className={summary.observeReady ? undefined : "idle"} />
                {summary.observeReady} of {summary.total} ready to observe
              </span>
              <button
                type="button"
                aria-pressed={showReady}
                onClick={() => setFilters(showReady ? EMPTY_FILTERS : { ...EMPTY_FILTERS, readiness: "ready" })}
              >
                {showReady ? "Show all" : "Show ready"}
              </button>
            </div>
          ) : null}
        </div>
        <div className="ov-hero-copy">
          <div className="ov-hero-eb">
            <span className="ov-eyebrow">Automate / Plays</span>
            {error && data ? (
              <span className="ov-fresh stale" role="status">
                <i aria-hidden />
                Could not refresh
                <button type="button" onClick={() => void mutate()}>
                  Retry
                </button>
              </span>
            ) : plays.length ? (
              <span className="ov-fresh">
                <i aria-hidden />
                {isValidating ? "Refreshing..." : `${summary.total} plays in your workspace`}
              </span>
            ) : null}
          </div>
          <h1 id="plays-hero">Plays</h1>
          <p className="ov-lead">
            Proven moves your agents can run, from watching quietly to acting on your behalf. Start every play in
            Observe, then grant more authority when the results earn it.
          </p>
          <div className="ov-stats">
            <StatButton
              value={loading ? null : summary.readyToTurnOn}
              label="Ready to turn on"
              tone="green"
              onClick={() => setFilters({ ...EMPTY_FILTERS, readiness: "ready", tier: "off" })}
            />
            <StatButton
              value={loading ? null : summary.tiers.recommend}
              label="Recommending"
              onClick={() => setFilters({ ...EMPTY_FILTERS, tier: "recommend" })}
            />
            <StatButton
              value={loading ? null : summary.tiers.act}
              label="Acting"
              onClick={() => setFilters({ ...EMPTY_FILTERS, tier: "act" })}
            />
            <StatButton
              value={loading ? null : summary.needsConnector}
              label="Needs a connector"
              tone={summary.needsConnector ? "amber" : undefined}
              onClick={() => setFilters({ ...EMPTY_FILTERS, readiness: "connector" })}
            />
          </div>
          <div className="ov-actions">
            <Link className="ov-btn dark" href="/marketplace">
              Browse the play library
            </Link>
            <AskGravitreSummonButton
              className="au-ask"
              label="Ask Gravitre which play fits"
              prompt="Which of my plays fits my goals best right now, and what would it need to start in Observe?"
            />
          </div>
        </div>
      </section>

      {error && !data ? (
        <section className="ov-panel" role="alert">
          <div className="ov-empty">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img src="/illustrations/moment-error.svg" alt="" width={160} />
            <b>Could not load plays</b>
            <p>{error instanceof Error ? error.message : "Unknown error"}</p>
            <button type="button" className="ov-btn sm" onClick={() => void mutate()}>
              Try again
            </button>
          </div>
        </section>
      ) : null}

      {plays.length ? (
        <section className="au-features" aria-label="Authority levels">
          {TIERS.map((tier) => {
            const count = summary.tiers[tier.tier]
            const share = shareOf(count, summary.total)
            return (
              <button
                key={tier.tier}
                type="button"
                className={cn("au-feature", `tone-${tier.tier}`)}
                aria-pressed={filters.tier === tier.tier}
                onClick={() => setFilters(filters.tier === tier.tier ? EMPTY_FILTERS : { ...EMPTY_FILTERS, tier: tier.tier })}
              >
                <div className="au-feature-art">
                  {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                  <img src={tier.art} alt={tier.alt} />
                  <span className="au-count">
                    <i aria-hidden />
                    {count} {count === 1 ? "play" : "plays"}
                  </span>
                </div>
                <div className="au-feature-body">
                  <span className="au-eyebrow">
                    {tier.n} · {TIER_LABEL[tier.tier]}
                  </span>
                  <b>{tier.title}</b>
                  <p>{tier.body}</p>
                  <div className="au-share" aria-label={`${share}% of plays are in ${TIER_LABEL[tier.tier]}`}>
                    <span className="track">
                      <span style={{ width: `${share}%` }} />
                    </span>
                    <small>{share}% of plays</small>
                  </div>
                </div>
              </button>
            )
          })}
        </section>
      ) : null}

      {!error || data ? (
        <section className="ov-panel" aria-labelledby="plays-list">
          <div className="ov-band">
            <div className="ov-band-l">
              <span className="ov-dots" aria-hidden>
                <i />
                <i />
                <i />
              </span>
              <h2 id="plays-list">Your plays</h2>
            </div>
            <div className="ov-seg" role="group" aria-label="Filter by authority">
              {tierCounts.map((item) => (
                <button key={item.id} type="button" aria-pressed={filters.tier === item.id} onClick={() => setFilter("tier", item.id)}>
                  <span className={cn("d", item.dot)} aria-hidden />
                  {item.label}
                  <span className="c">{loading ? "" : item.count}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="au-tools">
            <label className="ov-search">
              <Search size={16} aria-hidden />
              <span className="ov-sr">Search plays</span>
              <input
                type="search"
                placeholder="Search plays, outcomes or apps"
                value={filters.query}
                onChange={(e) => setFilter("query", e.target.value)}
              />
            </label>
            <label className="au-field">
              Department
              <select value={filters.department} onChange={(e) => setFilter("department", e.target.value)}>
                <option value="all">All</option>
                {departments.map((key) => (
                  <option key={key || "cross"} value={key}>
                    {departmentLabel(key)}
                  </option>
                ))}
              </select>
            </label>
            <label className="au-field">
              Readiness
              <select
                value={filters.readiness}
                onChange={(e) => setFilter("readiness", e.target.value as PlayFilters["readiness"])}
              >
                <option value="all">All</option>
                <option value="ready">Ready to observe</option>
                <option value="connector">Needs a connector</option>
                <option value="setup">Needs setup</option>
              </select>
            </label>
            <div className="ov-seg" role="group" aria-label="Layout">
              {VIEWS.map(({ id, label, icon: Icon }) => (
                <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
                  <Icon size={14} aria-hidden />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="au-split">
            <div className="au-main">
              {loading ? (
                <div className="au-cards" aria-busy="true">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="au-card tone-off" style={{ minHeight: 150 }} />
                  ))}
                </div>
              ) : plays.length === 0 ? (
                <div className="ov-empty">
                  {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                  <img src="/illustrations/moment-welcome.svg" alt="" width={160} />
                  <b>No plays in this workspace</b>
                  <p>Plays appear here when the catalog returns them for your organization. Nothing is invented when the list is empty.</p>
                </div>
              ) : visible.length === 0 ? (
                <div className="ov-empty">
                  <b>No plays match these filters</b>
                  <button type="button" className="ov-linkbtn" onClick={() => setFilters(EMPTY_FILTERS)}>
                    Clear filters
                  </button>
                </div>
              ) : view === "cards" ? (
                <div className="au-cards">
                  {paged.rows.map((item) => (
                    <PlayCard
                      key={item.play.key}
                      item={item}
                      selected={selected?.play.key === item.play.key}
                      onSelect={() => setSelectedKey(item.play.key)}
                    />
                  ))}
                </div>
              ) : view === "board" ? (
                <div className="au-board">
                  {TIER_ORDER.map((tier) => {
                    const column = visible.filter((item) => tierOf(item) === tier)
                    return (
                      <section key={tier} className={cn("au-col", `tone-${tier}`)} aria-label={TIER_LABEL[tier]}>
                        <header>
                          <TierChip tier={tier} />
                          <small>{column.length}</small>
                        </header>
                        {column.length === 0 ? (
                          <p className="au-col-empty">No plays here.</p>
                        ) : (
                          column.map((item) => (
                            <PlayCard
                              key={item.play.key}
                              item={item}
                              compact
                              selected={selected?.play.key === item.play.key}
                              onSelect={() => setSelectedKey(item.play.key)}
                            />
                          ))
                        )}
                      </section>
                    )
                  })}
                </div>
              ) : (
                <div className="au-table-wrap">
                  <table className="au-table">
                    <thead>
                      <tr>
                        <th scope="col">Play</th>
                        <th scope="col">Authority</th>
                        <th scope="col">Department</th>
                        <th scope="col">Readiness</th>
                        <th scope="col" className="num">Workflows</th>
                        <th scope="col" className="num">Verified results</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paged.rows.map((item) => (
                        <tr
                          key={item.play.key}
                          aria-selected={selected?.play.key === item.play.key}
                          onClick={() => setSelectedKey(item.play.key)}
                        >
                          <td>
                            <button type="button" className="au-name" onClick={() => setSelectedKey(item.play.key)}>
                              <b>{item.play.name}</b>
                              <span>{item.play.objective}</span>
                            </button>
                          </td>
                          <td className={`tone-${tierOf(item)}`}>
                            <TierChip tier={tierOf(item)} />
                          </td>
                          <td>
                            <span className="au-tag">{departmentLabel(departmentKey(item))}</span>
                          </td>
                          <td>
                            <ReadinessBadge state={readinessOf(item)} />
                          </td>
                          <td className="num">{item.workflowBindingCount}</td>
                          <td className="num">{verifiedByPlay.get(item.play.key) ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {visible.length > 0 && view !== "board" ? (
                <div className="au-foot">
                  <span>
                    Showing{" "}
                    <b>
                      {paged.from} to {paged.to}
                    </b>{" "}
                    of {visible.length}
                  </span>
                  <AuPages page={paged.page} pageCount={paged.pageCount} onPage={setPage} label="Play pages" />
                </div>
              ) : null}
            </div>

            {selected ? (
              <PlaySide
                item={selected}
                verified={verifiedByPlay.get(selected.play.key) ?? 0}
                onGrant={(mode, label) => setGrantTarget({ item: selected, mode, label })}
              />
            ) : null}
          </div>
        </section>
      ) : null}

      <AlertDialog open={Boolean(grantTarget)} onOpenChange={(open) => (!open && !granting ? setGrantTarget(null) : undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {grantTarget?.label} for {grantTarget?.item.play.name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {grantTarget?.mode === "ACT WITH APPROVAL"
                ? "The play can prepare changes in your connected apps. Every change waits in Approvals until a person approves it. You can step it back to Recommend at any time from the play."
                : grantTarget?.mode === "RECOMMEND"
                  ? "The play will send its suggested moves to you as recommendations. Nothing changes in your apps until you act on one."
                  : "The play will start reading your connected data and report what it would do. Nothing changes in your apps."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={granting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={granting}
              onClick={(event) => {
                event.preventDefault()
                void grant()
              }}
            >
              {granting ? "Saving..." : grantTarget?.label}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function StatButton({
  value,
  label,
  tone,
  onClick,
}: {
  value: number | null
  label: string
  tone?: "green" | "amber" | "red"
  onClick: () => void
}) {
  return (
    <button type="button" className={cn("ov-stat", tone)} onClick={onClick}>
      <span className="v">{value === null ? <span className="ov-skel-n" aria-hidden /> : value}</span>
      <span className="k">{label}</span>
    </button>
  )
}

function PlayCard({
  item,
  selected,
  compact = false,
  onSelect,
}: {
  item: PlayListItem
  selected: boolean
  compact?: boolean
  onSelect: () => void
}) {
  const tier = tierOf(item)
  return (
    <button type="button" className={cn("au-card", `tone-${tier}`)} aria-pressed={selected} onClick={onSelect}>
      <span className="row">
        <TierChip tier={tier} />
        <small>{workflowsLabel(item.workflowBindingCount)}</small>
      </span>
      <b>{item.play.name}</b>
      {compact ? null : <p>{item.play.objective}</p>}
      <span className="row foot">
        <span className="au-tag">{departmentLabel(departmentKey(item))}</span>
        <ReadinessBadge state={readinessOf(item)} />
      </span>
    </button>
  )
}

function PlaySide({
  item,
  verified,
  onGrant,
}: {
  item: PlayListItem
  verified: number
  onGrant: (mode: PlayOperatingMode, label: string) => void
}) {
  const tier = tierOf(item)
  const dept = departmentKey(item)
  const next = nextGrant(item)
  const readiness = readinessOf(item)
  const chips = connectorChips(item)
  return (
    <aside className={cn("au-side", `tone-${tier}`)} aria-label={`${item.play.name} details`}>
      <div className="au-side-art">
        {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
        <img src={departmentArt(dept)} alt="" />
      </div>
      <div className="ov-chips">
        <TierChip tier={tier} />
        <span className="au-tag">{departmentLabel(dept)}</span>
      </div>
      <h3>{item.play.name}</h3>
      <p className="desc">{item.play.objective}</p>

      <span className="au-eyebrow">Authority</span>
      <ol className="au-ladder" aria-label="Authority levels">
        {ladder(item).map((rung) => (
          <li key={rung.tier} className={cn("au-rung", rung.state, `tone-${rung.tier}`)}>
            <b>{rung.label}</b>
            <span>{rung.state === "current" ? "Current" : rung.state === "earned" ? "Earned" : "Locked"}</span>
          </li>
        ))}
      </ol>

      <div className="au-facts">
        <div className="au-fact">
          <b>{verified}</b>
          <span>Verified results</span>
        </div>
        <div className="au-fact">
          <b>{item.workflowBindingCount}</b>
          <span>Workflows linked</span>
        </div>
      </div>

      {chips.length ? (
        <>
          <span className="au-eyebrow">Connectors</span>
          <div className="au-connectors">
            {chips.map((chip, index) => (
              <span key={`${chip.vendor}-${index}`} className={chip.ready ? undefined : "off"}>
                <i aria-hidden />
                {vendorName(chip.vendor)}
                <span className="ov-sr">{chip.ready ? " connected" : " not connected"}</span>
              </span>
            ))}
          </div>
        </>
      ) : null}

      {readiness !== "ready" && item.readiness.blockers?.[0] ? (
        <p className="ov-note">{item.readiness.blockers[0]}</p>
      ) : null}

      <div className="au-side-foot">
        {next ? (
          <button type="button" className="ov-btn sm green" onClick={() => onGrant(next.mode, next.label)}>
            {next.label}
          </button>
        ) : readiness !== "ready" ? (
          <Link className="ov-btn sm green" href={setupHref(item.readiness)}>
            Finish setup
          </Link>
        ) : null}
        <Link className="ov-btn sm" href={`/plays/${item.play.key}`}>
          Preview a run <ArrowRight size={14} aria-hidden />
        </Link>
      </div>
    </aside>
  )
}
