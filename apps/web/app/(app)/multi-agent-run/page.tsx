"use client"

// Agents > Multi-agent ("Gravitre Agents" design): council runs over real agents and runs.
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { WsPage } from "@/components/workspace/ws-page"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { StartSwarmDialog, type SwarmStartPreset } from "@/components/agent-swarm/start-swarm-dialog"
import { SwarmRunDetailPanel } from "@/components/agent-swarm/swarm-run-detail-panel"
import { CouncilPreview, DEPT_DOT, councilSeats } from "@/components/agents/suite/council-preview"
import "@/components/agents/roster/roster.css"
import "@/components/agents/suite/agents-suite.css"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import { agentSwarmApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { ensureSelectedOrg } from "@/lib/org-context"
import { formatSwarmReadableText } from "@/lib/swarm-result-format"
import { DEPARTMENT_BY_ID, normalizeAgentsPayload, toRosterAgent, type RosterAgent } from "@/lib/agents-roster"
import type { AgentSwarmRun } from "@/types/api"
import { cn } from "@/lib/utils"

const ACTIVE = new Set(["pending", "running", "aggregating"])

type RunFilter = "all" | "active" | "completed" | "review"

const FILTERS: Array<{ id: RunFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "completed", label: "Completed" },
  { id: "review", label: "Needs review" },
]

/** Starter questions: who should sit on the council for each. */
const STARTERS: Array<{ text: string; teams: AgentDepartmentId[] }> = [
  { text: "Which accounts should Sales prioritise this week?", teams: ["sales", "customer_success", "finance"] },
  { text: "Where is marketing spend not paying back?", teams: ["marketing", "finance", "sales"] },
  { text: "Which customers are at risk this quarter?", teams: ["customer_success", "sales", "security"] },
  { text: "Are we ready to close the month?", teams: ["finance", "operations", "general"] },
]

const STATUS_LABEL: Record<string, string> = {
  pending: "Starting",
  running: "Talking it through",
  aggregating: "Agreeing",
  completed: "Recommended",
  failed: "Needs review",
  cancelled: "Stopped",
}

function deptName(id: AgentDepartmentId) {
  return DEPARTMENT_BY_ID.get(id)?.name ?? id
}

function relative(iso: string | null | undefined) {
  if (!iso) return null
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return null
  }
}

function needsReview(run: AgentSwarmRun) {
  return run.status === "failed"
}

function CouncilIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="8" r="3" />
      <circle cx="5" cy="11" r="2" />
      <circle cx="19" cy="11" r="2" />
      <path d="M7 19a5 5 0 0 1 10 0M2 18a3 3 0 0 1 4-2.8M22 18a3 3 0 0 0-4-2.8" />
    </svg>
  )
}

export default function MultiAgentRunPage() {
  return (
    <AppShell title="Multi-agent runs">
      <Suspense fallback={null}>
        <MultiAgentRunContent />
      </Suspense>
    </AppShell>
  )
}

function MultiAgentRunContent() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [orgError, setOrgError] = useState<string | null>(null)
  const [orgAttempt, setOrgAttempt] = useState(0)
  const [orgId, setOrgId] = useState<string | null>(null)
  const detailBusy = useRef(false)
  const [startOpen, setStartOpen] = useState(false)
  const [preset, setPreset] = useState<SwarmStartPreset | null>(null)
  const [pick, setPick] = useState(0)
  const [filter, setFilter] = useState<RunFilter>("all")
  const [selectedId, setSelectedId] = useState<string | null>(() => searchParams.get("runId"))

  const selectRun = useCallback(
    (id: string) => {
      if (detailBusy.current) return
      setSelectedId(id)
      router.replace(`${APP_ROUTES.multiAgentRun}?runId=${id}`, { scroll: false })
    },
    [router],
  )

  const prevStatusRef = useRef<Map<string, string>>(new Map())
  const notifiedRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    setOrgId(null)
    setOrgError(null)
    if (user)
      void ensureSelectedOrg(true)
        .then((id) => {
          if (!cancelled) {
            setOrgId(id)
            if (!id) setOrgError("Workspace membership is required to load runs.")
          }
        })
        .catch(() => {
          if (!cancelled) setOrgError("Could not load your workspace. Try again.")
        })
    return () => {
      cancelled = true
    }
  }, [user, orgAttempt])

  useEffect(() => {
    setSelectedId(searchParams.get("runId"))
  }, [searchParams])

  const swrKey = orgId ? `agent-swarm/runs:${orgId}` : null
  const { data, error, isLoading, isValidating, mutate } = useSWR(swrKey, () => agentSwarmApi.list({ limit: 30 }), {
    refreshInterval: (latest) => ((latest?.runs ?? []).some((r) => ACTIVE.has(r.status)) ? 5000 : 0),
  })
  const {
    data: agentsData,
    error: agentsError,
    mutate: mutateAgents,
  } = useSWR(user ? "/api/agents" : null, apiFetcher, { dedupingInterval: 2000 })

  const runs = useMemo(() => data?.runs ?? [], [data])
  const agents: RosterAgent[] = useMemo(
    () => normalizeAgentsPayload(agentsData).map((raw) => toRosterAgent(raw, undefined)),
    [agentsData],
  )
  const ready = useMemo(() => agents.filter((a) => a.state !== "blocked" && a.state !== "not_set_up"), [agents])

  useEffect(() => {
    for (const run of runs) {
      const previous = prevStatusRef.current.get(run.id)
      prevStatusRef.current.set(run.id, run.status)
      if (run.status === "completed" && previous && previous !== "completed" && !notifiedRef.current.has(run.id)) {
        notifiedRef.current.add(run.id)
        const summary = formatSwarmReadableText(run.finalRecommendation, 140)
        toast.success("The council has a recommendation", {
          description: summary || run.objective,
          action: { label: "View", onClick: () => selectRun(run.id) },
        })
      }
    }
  }, [runs, selectRun])

  const selectedRun = runs.find((run) => run.id === selectedId)
  usePublishGravitreAISelection(
    selectedRun ? { kind: "multi-agent-run", id: selectedRun.id, label: selectedRun.objective } : null,
  )

  const stats = useMemo(
    () => ({
      active: runs.filter((r) => ACTIVE.has(r.status)).length,
      completed: runs.filter((r) => r.status === "completed").length,
      review: runs.filter(needsReview).length,
    }),
    [runs],
  )
  const latest = useMemo(
    () => runs.find((r) => r.status === "completed" && (r.finalRecommendation ?? "").trim()) ?? null,
    [runs],
  )

  const labels = useMemo(() => new Map(agents.map((a) => [a.department, a.departmentLabel] as const)), [agents])
  const starter = STARTERS[pick]
  const seats = useMemo(() => councilSeats(agents, starter.teams, labels), [agents, starter, labels])
  const councilSize = useMemo(() => new Set(ready.map((a) => a.department)).size, [ready])

  const visibleRuns = useMemo(() => {
    if (filter === "active") return runs.filter((r) => ACTIVE.has(r.status))
    if (filter === "completed") return runs.filter((r) => r.status === "completed")
    if (filter === "review") return runs.filter(needsReview)
    return runs
  }, [runs, filter])

  function openStart(next: SwarmStartPreset | null) {
    setPreset(next)
    setStartOpen(true)
  }

  /** One subtask per department on the question, each given to that department's best ready agent. */
  function startStarter(index: number) {
    const s = STARTERS[index]
    const picks = councilSeats(agents, s.teams, labels).filter((seat) => seat.involved && seat.agent)
    openStart({
      objective: s.text,
      subtasks: picks.map((seat) => ({
        agentId: seat.agent!.id,
        task: `From the ${seat.departmentLabel} point of view: ${s.text} Share the evidence behind your answer.`,
      })),
    })
  }

  function handleStarted(id: string) {
    void mutate()
    selectRun(id)
  }

  function handleCloseDetail() {
    if (detailBusy.current) return
    setSelectedId(null)
    router.replace(APP_ROUTES.multiAgentRun, { scroll: false })
  }

  const refresh = () => {
    void mutate()
    void mutateAgents()
  }

  const loadingRuns = !orgId || (isLoading && runs.length === 0)

  return (
    <WsPage>
      <div className="rs-tabs">
        <AgentsHubTabs active="multi-agent" />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 24, paddingTop: 24 }}>
        <div className="ma-top">
          <section aria-labelledby="ma-heading" className="as-panel ma-hero">
            <div className="ma-hero-head">
              <div>
                <h1 id="ma-heading">Multi-agent runs</h1>
                <p>Put several agents on one question. They talk it through and hand you one recommendation.</p>
              </div>
              <div className="ma-actions">
                {selectedRun ? (
                  <AskGravitreSummonButton
                    className="rs-ask"
                    label="Review this run"
                    prompt="Review the selected multi-agent run’s reported contributions, disagreements and final recommendation."
                  />
                ) : null}
                <button type="button" className="gv-btn outline" onClick={refresh} disabled={!orgId || isValidating}>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                    className={cn(isValidating && "animate-spin motion-reduce:animate-none")}
                  >
                    <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
                    <path d="M21 3v5h-5" />
                  </svg>
                  Refresh
                </button>
                <button type="button" className="gv-btn dark" onClick={() => openStart(null)} disabled={!orgId}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  Start a council run
                </button>
              </div>
            </div>
            <div className="ma-stats">
              <Link href="/agents?view=list" className="ma-stat ok">
                <span className="k">
                  <i />
                  Ready to join
                </span>
                <span className="v">{agentsData ? ready.length : "–"}</span>
              </Link>
              <button type="button" className="ma-stat" aria-pressed={filter === "active"} onClick={() => setFilter("active")}>
                <span className="k">
                  <i />
                  Active runs
                </span>
                <span className="v">{data ? stats.active : "–"}</span>
              </button>
              <button type="button" className="ma-stat" aria-pressed={filter === "completed"} onClick={() => setFilter("completed")}>
                <span className="k">
                  <i />
                  Completed
                </span>
                <span className="v">
                  {data ? stats.completed : "–"}
                  <small>last 30</small>
                </span>
              </button>
              <button
                type="button"
                className={cn("ma-stat", stats.review > 0 && "warn")}
                aria-pressed={filter === "review"}
                onClick={() => setFilter("review")}
              >
                <span className="k">
                  <i className={stats.review > 0 ? "warn" : "idle"} />
                  Needs you
                </span>
                <span className="v">
                  {data ? stats.review : "–"}
                  <small>{stats.review > 0 ? "to review" : "All clear"}</small>
                </span>
              </button>
            </div>
          </section>

          <section aria-labelledby="latest-heading" className="as-dark ma-latest">
            <span className="eb">Latest recommendation</span>
            <div className="art">
              {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
              <img src="/illustrations/agents-council-wide.svg" alt="" />
            </div>
            {latest ? (
              <>
                <h2 id="latest-heading">{latest.objective}</h2>
                <p>{formatSwarmReadableText(latest.finalRecommendation, 220)}</p>
                <div className="meta">
                  {latest.finalConfidence != null ? <span>{Math.round(latest.finalConfidence * 100)}% confidence</span> : null}
                  {relative(latest.completedAt ?? latest.updatedAt) ? <span>{relative(latest.completedAt ?? latest.updatedAt)}</span> : null}
                  <span>Advice only. Actions still wait for your approval.</span>
                </div>
                <div className="ma-actions">
                  <button type="button" className="as-gbtn" onClick={() => selectRun(latest.id)}>
                    Open recommendation
                  </button>
                  <button type="button" className="as-obtn" onClick={() => openStart(null)} disabled={!orgId}>
                    Start another run
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 id="latest-heading">No council runs yet</h2>
                <p>When your agents agree on their first recommendation, it will be featured right here.</p>
                <div className="ma-actions">
                  <button type="button" className="as-gbtn" onClick={() => startStarter(pick)} disabled={!orgId}>
                    Start your first run
                  </button>
                </div>
              </>
            )}
          </section>
        </div>

        {orgError ? (
          <WorkSectionErrorCard
            title="Could not load workspace"
            message={orgError}
            onRetry={() => setOrgAttempt((n) => n + 1)}
          />
        ) : null}
        {error ? (
          <WorkSectionErrorCard
            title="Couldn't load multi-agent runs"
            message="We couldn't fetch your run history. Check your connection and try again."
            error={error}
            onRetry={() => void mutate()}
          />
        ) : null}
        {agentsError ? (
          <WorkSectionErrorCard
            title="Couldn't load your agents"
            message="The council preview needs your roster. Try again."
            error={agentsError}
            onRetry={() => void mutateAgents()}
          />
        ) : null}

        <section aria-labelledby="council-heading" className="as-panel as-split">
          <div className="as-split-side">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div className="as-h2-row">
                <span className="as-sq" style={{ background: "#2e9e5b" }} />
                <h2 id="council-heading" className="as-h2">
                  Council
                </h2>
                <span className="n">{agentsData ? councilSize : ""}</span>
              </div>
              <p className="as-copy">
                Agents from different departments split one question, talk it through and agree on one recommendation.
              </p>
            </div>
            <ol className="ma-steps">
              {[
                ["Ask", "You set one business question."],
                ["Talk it through", "Agents message each other and share findings."],
                ["Agree", "The council weighs evidence and notes dissent."],
                ["Recommend", "One answer, with the sources behind it."],
              ].map(([title, body], i) => (
                <li key={title}>
                  <span className="num">{i + 1}</span>
                  <span>
                    <b>{title}</b>
                    <span>{body}</span>
                  </span>
                </li>
              ))}
            </ol>
            <div className="as-note">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--gv-amber-text)" strokeWidth="2" strokeLinecap="round" aria-hidden style={{ flex: "none", marginTop: 2 }}>
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v5M12 16h.01" />
              </svg>
              <span>
                A recommendation is advice, not proof that anything was done. Actions still wait for your approval, and your{" "}
                <Link href={APP_ROUTES.training}>guardrails</Link> apply inside every run.
              </span>
            </div>
            <button
              type="button"
              className="gv-btn dark"
              style={{ alignSelf: "flex-start", marginTop: "auto" }}
              onClick={() => openStart(null)}
              disabled={!orgId}
            >
              Give the council a question
            </button>
          </div>
          <div className="as-split-main">
            <div className="ma-preview-head">
              <span className="ma-live">
                <i />
                Live preview
              </span>
              <span className="ma-objective" title={starter.text}>
                {starter.text}
              </span>
            </div>
            <div className="ma-stage">
              <div>
                <CouncilPreview seats={seats} />
              </div>
            </div>
            {agentsData && agents.length === 0 ? (
              <p className="as-copy">
                You have no agents yet. <Link href="/agents/new">Create one</Link> to seat it on the council.
              </p>
            ) : null}
          </div>
        </section>

        <section aria-labelledby="runs-heading" className="as-panel as-split">
          <div className="as-split-side" style={{ gap: 14 }}>
            <div className="as-h2-row">
              <span className="as-sq" style={{ background: "#3d6fd1" }} />
              <h2 id="runs-heading" className="as-h2">
                Recent runs
              </h2>
              <span className="n">{data ? runs.length : ""}</span>
            </div>
            <p className="as-copy">
              {runs.length === 0
                ? "Nothing yet. Preview a starter question in the council above, then run it."
                : "Your latest 30 council runs. Open one to see each agent's part, the evidence and the recommendation."}
            </p>
            <div role="group" aria-label="Filter runs" className="as-filter">
              {FILTERS.map((f) => (
                <button key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className="as-split-main" style={{ padding: 20 }}>
            {loadingRuns && !orgError ? (
              <div className="ma-cards" aria-busy="true" aria-label="Loading runs">
                {Array.from({ length: 2 }).map((_, i) => (
                  <div key={i} className="gv-skel as-skel-card" />
                ))}
              </div>
            ) : (
              <>
                {visibleRuns.length > 0 ? (
                  <div className="ma-cards">
                    {visibleRuns.map((run) => (
                      <RunCard
                        key={run.id}
                        run={run}
                        selected={run.id === selectedId}
                        onSelect={() => (selectedId === run.id ? handleCloseDetail() : selectRun(run.id))}
                      />
                    ))}
                  </div>
                ) : runs.length > 0 ? (
                  <p className="as-copy">No runs match this filter.</p>
                ) : null}
                {filter === "all" ? (
                  <>
                    {runs.length > 0 ? <p className="ma-sub">Starter questions</p> : null}
                    <div className="ma-cards">
                      {STARTERS.map((s, i) => (
                        <article key={s.text} className="ma-card">
                          <div className="ma-card-head">
                            <div className="ma-card-ic">
                              <CouncilIcon />
                            </div>
                            <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                              <span className="ma-card-title">{s.text}</span>
                              <span className="ma-card-sub">{s.teams.length} agents</span>
                            </div>
                          </div>
                          <div className="ma-tags">
                            {s.teams.map((t) => (
                              <span key={t} className="as-tag">
                                <span className="rs-ddot" style={{ background: DEPT_DOT[t], width: 7, height: 7 }} />
                                {deptName(t)}
                              </span>
                            ))}
                          </div>
                          <div className="ma-card-foot">
                            {i === pick ? (
                              <span className="ma-showing">
                                <i />
                                Showing in preview
                              </span>
                            ) : (
                              <button type="button" className="ma-preview-link" onClick={() => setPick(i)}>
                                Preview
                              </button>
                            )}
                            <button type="button" className="as-gbtn sm" onClick={() => startStarter(i)} disabled={!orgId}>
                              Run this
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  </>
                ) : null}
              </>
            )}
          </div>
        </section>
      </div>

      <SelectionInspector
        open={Boolean(selectedId)}
        onOpenChange={(open) => {
          if (!open) handleCloseDetail()
        }}
        title="Multi-agent run"
        description="Subtasks, council evidence and execution controls."
      >
        {selectedId ? (
          <SwarmRunDetailPanel
            key={selectedId}
            swarmRunId={selectedId}
            hideClose
            onBusyChange={(busy) => {
              detailBusy.current = busy
            }}
            onClose={handleCloseDetail}
            onMutateList={() => void mutate()}
          />
        ) : null}
      </SelectionInspector>

      <StartSwarmDialog
        open={startOpen}
        onOpenChange={(open) => {
          setStartOpen(open)
          if (!open) setPreset(null)
        }}
        preset={preset}
        onStarted={handleStarted}
      />
    </WsPage>
  )
}

function RunCard({ run, selected, onSelect }: { run: AgentSwarmRun; selected: boolean; onSelect: () => void }) {
  const preview = run.finalRecommendation ? formatSwarmReadableText(run.finalRecommendation, 160) : null
  const when = relative(run.completedAt ?? run.createdAt)
  const active = ACTIVE.has(run.status)
  const tone = run.status === "failed" ? "warn" : run.status === "cancelled" ? "idle" : ""
  const agents = run.subtasks?.length ?? 0
  return (
    <button type="button" className="ma-card" aria-pressed={selected} onClick={onSelect}>
      <div className="ma-card-head">
        <div className={cn("ma-card-ic", tone)}>
          <CouncilIcon />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <span className="ma-card-title">{run.objective}</span>
          <span className="ma-card-sub">
            {[agents > 0 ? `${agents} agents` : null, when].filter(Boolean).join(" · ") || "Not reported"}
          </span>
        </div>
      </div>
      {preview ? (
        <p className="ma-card-body">{preview}</p>
      ) : run.status === "failed" && run.errorMessage ? (
        <p className="ma-card-body">{run.errorMessage}</p>
      ) : null}
      <div className="ma-card-foot">
        <span className={cn("gv-pill", run.status === "completed" ? "brand" : run.status === "failed" ? "red" : active ? "blue" : "neutral")}>
          {STATUS_LABEL[run.status] ?? "Not reported"}
        </span>
        <span className="ma-card-sub">Open</span>
      </div>
    </button>
  )
}
