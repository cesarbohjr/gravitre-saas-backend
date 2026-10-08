"use client"

// Agents > Roster: Team / List / Work map (Workspace redesign v1). ?view=team|list|graph
import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR, { mutate as globalMutate } from "swr"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { RosterTeamView } from "@/components/agents/roster/roster-team-view"
import { RosterListView } from "@/components/agents/roster/roster-list-view"
import { RosterWorkMap } from "@/components/agents/roster/roster-work-map"
import "@/components/agents/roster/roster.css"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useAgentsFleetPrefs } from "@/hooks/use-agents-fleet-prefs"
import {
  isRosterView,
  normalizeAgentsPayload,
  rosterStatsKey,
  toRosterAgent,
  type RosterAgent,
  type RosterStatsPayload,
  type RosterView,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"

const AGENTS_REFRESH_MS = 30_000

const VIEWS: Array<{ id: RosterView; label: string; hint: string; icon: React.ReactNode }> = [
  {
    id: "team",
    label: "Team",
    hint: "Meet your crew",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <circle cx="8" cy="9" r="3" />
        <circle cx="16" cy="9" r="3" />
        <path d="M3 19c.8-3 2.8-4.5 5-4.5s4.2 1.5 5 4.5M11 19c.8-3 2.8-4.5 5-4.5s4.2 1.5 5 4.5" />
      </svg>
    ),
  },
  {
    id: "list",
    label: "List",
    hint: "Manage at scale",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
        <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
      </svg>
    ),
  },
  {
    id: "graph",
    label: "Graph",
    hint: "See how work flows",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <circle cx="12" cy="12" r="2.5" />
        <circle cx="5" cy="6" r="2" />
        <circle cx="19" cy="6" r="2" />
        <circle cx="5" cy="18" r="2" />
        <circle cx="19" cy="18" r="2" />
        <path d="m6.6 7.2 3.4 3.3M17.4 7.2 14 10.5M6.6 16.8l3.4-3.3M17.4 16.8 14 13.5" />
      </svg>
    ),
  },
]

function RosterSkeleton() {
  return (
    <div className="gv-card" style={{ padding: 28, display: "grid", gap: 14 }} aria-busy="true" aria-label="Loading agents">
      <div className="gv-skel" style={{ width: 120 }} />
      <div className="gv-skel" style={{ width: "50%", height: 28 }} />
      <div className="gv-skel" style={{ width: "70%" }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 12 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="gv-skel" style={{ height: 72, borderRadius: 12 }} />
        ))}
      </div>
    </div>
  )
}

function AgentsRoster() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const { prefs, hydrated, setView } = useAgentsFleetPrefs()
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)
  const [selected, setSelected] = useState<RosterAgent | null>(null)

  const param = searchParams.get("view")
  const view: RosterView = isRosterView(param) ? param : prefs.view

  // Keep ?view= in the URL so every roster view is shareable.
  useEffect(() => {
    if (!hydrated || isRosterView(param)) return
    const next = new URLSearchParams(searchParams.toString())
    next.set("view", prefs.view)
    router.replace(`${pathname || "/agents"}?${next.toString()}`, { scroll: false })
  }, [hydrated, param, pathname, prefs.view, router, searchParams])

  useEffect(() => {
    if (isRosterView(param) && param !== prefs.view && hydrated) setView(param)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- remember the last view the URL asked for
  }, [param, hydrated])

  const { data, error, isLoading, mutate } = useSWR(user ? "/api/agents" : null, apiFetcher, {
    revalidateOnFocus: true,
    refreshInterval: AGENTS_REFRESH_MS,
    dedupingInterval: 2000,
  })
  const statsKey = useMemo(() => (user ? rosterStatsKey() : null), [user])
  const {
    data: stats,
    error: statsError,
    mutate: mutateStats,
  } = useSWR<RosterStatsPayload>(statsKey, apiFetcher, {
    revalidateOnFocus: true,
    refreshInterval: AGENTS_REFRESH_MS,
    dedupingInterval: 2000,
  })
  const statsAvailable = Boolean(stats && !statsError)

  const agents = useMemo(
    () => normalizeAgentsPayload(data).map((raw) => toRosterAgent(raw, statsAvailable ? stats : undefined)),
    [data, stats, statsAvailable],
  )

  usePublishGravitreAISelection(selected ? { kind: "agent", id: selected.id, label: selected.name } : null)
  useEffect(() => setSelected(null), [view])

  const refresh = useCallback(async () => {
    await Promise.all([mutate(), mutateStats()])
  }, [mutate, mutateStats])

  const viewHref = (id: RosterView) => {
    const next = new URLSearchParams()
    next.set("view", id)
    return `${pathname || "/agents"}?${next.toString()}`
  }

  return (
    <WsPage>
      <div className="rs-tabs">
        <AgentsHubTabs active="roster" />
      </div>
      <div className="rs-toolbar">
        <nav aria-label="Roster view" className="gv-card rs-views">
          {VIEWS.map((v) => (
            <Link
              key={v.id}
              href={viewHref(v.id)}
              replace
              scroll={false}
              className={cn("rs-view", view === v.id && "on")}
              aria-current={view === v.id ? "page" : undefined}
              onClick={() => setView(v.id)}
            >
              <span className="ic">{v.icon}</span>
              <span>
                <b>{v.label}</b>
                <small>{v.hint}</small>
              </span>
            </Link>
          ))}
        </nav>
        <div className="rs-actions">
          <AskGravitreSummonButton className="rs-ask" />
          <button
            type="button"
            className="gv-btn outline"
            onClick={() => setMesonWizardOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={mesonWizardOpen}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--gv-blue)" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M4 8h12l-3-3M4 16h12l-3 3" />
            </svg>
            Build with Meson
          </button>
          <Link className="gv-btn dark" href="/agents/new">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
            New agent
          </Link>
        </div>
      </div>

      {error ? (
        <div className="gv-card rs-empty">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
          <img src="/illustrations/moment-error.svg" alt="" />
          <h2>Could not load agents</h2>
          <p>We couldn&apos;t reach the agents service. Check your connection and try again.</p>
          <button type="button" className="gv-btn dark" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      ) : isLoading && agents.length === 0 ? (
        <RosterSkeleton />
      ) : agents.length === 0 ? (
        <div className="gv-card rs-empty">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
          <img src="/illustrations/moment-welcome.svg" alt="" />
          <h2>No agents yet</h2>
          <p>Create your first teammate to start delegating work.</p>
          <Link className="gv-btn dark" href="/agents/new">
            New agent
          </Link>
        </div>
      ) : view === "list" ? (
        <RosterListView
          agents={agents}
          statsAvailable={statsAvailable}
          initialStatus={searchParams.get("status")}
          initialDept={searchParams.get("dept")}
          onChanged={refresh}
          onSelectionChange={setSelected}
        />
      ) : view === "graph" ? (
        <RosterWorkMap
          agents={agents}
          goals={statsAvailable ? stats?.goals ?? [] : []}
          statsAvailable={statsAvailable}
          initialTrace={searchParams.get("trace")}
          onGoalsChanged={() => void mutateStats()}
          onSelectAgent={setSelected}
        />
      ) : (
        <RosterTeamView agents={agents} statsAvailable={statsAvailable} days={stats?.days?.length ?? 0} />
      )}

      <MesonWizard
        open={mesonWizardOpen}
        onClose={() => setMesonWizardOpen(false)}
        onComplete={async (result) => {
          await globalMutate("/api/agents")
          if (result.agentId) {
            router.push(`/agents/${result.agentId}`)
            return
          }
          router.push("/agents")
        }}
      />
    </WsPage>
  )
}

export default function AgentsPage() {
  return (
    <AppShell title={SURFACE_COPY.pages.agents.title}>
      <Suspense fallback={null}>
        <AgentsRoster />
      </Suspense>
    </AppShell>
  )
}
