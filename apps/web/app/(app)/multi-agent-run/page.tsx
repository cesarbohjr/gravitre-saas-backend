"use client"

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { motion, useReducedMotion } from "framer-motion"
import { toast } from "sonner"
import { ChevronRight, Network, Plus, RefreshCw } from "lucide-react"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { Button } from "@/components/ui/button"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { TYPE } from "@/lib/design-system"
import {
  GravitreMetric,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { MultiAgentRunOverview } from "@/components/gravitre/multi-agent-run-overview"
import { agentSwarmApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg } from "@/lib/org-context"
import { formatSwarmReadableText } from "@/lib/swarm-result-format"
import type { AgentSwarmRun } from "@/types/api"
import { StartSwarmDialog } from "@/components/agent-swarm/start-swarm-dialog"
import { SwarmRunDetailPanel } from "@/components/agent-swarm/swarm-run-detail-panel"
import { SwarmRunStatusBadge } from "@/components/agent-swarm/swarm-status-badge"
import {
  isSwarmExecutionUnverified,
  SwarmVerificationLabel,
} from "@/components/agent-swarm/swarm-verification-label"
import { SwarmConvergenceDiagram } from "@/components/agent-swarm/swarm-convergence-diagram"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { cn } from "@/lib/utils"

const ACTIVE = new Set(["pending", "running", "aggregating"])

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "Not reported"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return "Not reported"
  }
}

export default function MultiAgentRunPage() {
  return (
    <AppShell title="Multi-Agent Run">
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
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    searchParams.get("runId"),
  )
  const selectRun = useCallback(
    (id: string) => {
      if (detailBusy.current) return
      setSelectedId(id)
      router.replace(`${APP_ROUTES.multiAgentRun}?runId=${id}`, {
        scroll: false,
      })
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
            if (!id)
              setOrgError("Workspace membership is required to load runs.")
          }
        })
        .catch(() => {
          if (!cancelled)
            setOrgError("Could not load your workspace. Try again.")
        })
    return () => {
      cancelled = true
    }
  }, [user, orgAttempt])

  useEffect(() => {
    const runId = searchParams.get("runId")
    setSelectedId(runId)
  }, [searchParams])

  const swrKey = orgId ? `agent-swarm/runs:${orgId}` : null
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    swrKey,
    () => agentSwarmApi.list({ limit: 30 }),
    {
      refreshInterval: (latest) => {
        const runs = latest?.runs ?? []
        return runs.some((r) => ACTIVE.has(r.status)) ? 5000 : 0
      },
    },
  )

  const runs = useMemo(() => data?.runs ?? [], [data])

  useEffect(() => {
    for (const run of runs) {
      const previous = prevStatusRef.current.get(run.id)
      prevStatusRef.current.set(run.id, run.status)
      if (
        run.status === "completed" &&
        previous &&
        previous !== "completed" &&
        !notifiedRef.current.has(run.id)
      ) {
        notifiedRef.current.add(run.id)
        const summary = formatSwarmReadableText(run.finalRecommendation, 140)
        toast.success("Multi-agent run complete", {
          description: summary || run.objective,
          action: {
            label: "View results",
            onClick: () => selectRun(run.id),
          },
        })
      }
    }
  }, [runs, selectRun])

  const selectedRun = runs.find(run => run.id === selectedId)
  usePublishGravitreAISelection(selectedRun ? { kind: "multi-agent-run", id: selectedRun.id, label: selectedRun.objective } : null)
  const stats = useMemo(() => {
    const active = runs.filter((r) => ACTIVE.has(r.status)).length
    const completed = runs.filter((r) => r.status === "completed").length
    return { active, completed, total: runs.length }
  }, [runs])

  function handleStarted(id: string) {
    void mutate()
    selectRun(id)
  }

  function handleCloseDetail() {
    if (detailBusy.current) return
    setSelectedId(null)
    router.replace(APP_ROUTES.multiAgentRun, { scroll: false })
  }

  return (
    <div className="relative min-h-full" data-composition="operate">
      <div className="relative z-10 mx-auto max-w-6xl space-y-6 p-4 pb-24 sm:p-6 sm:pb-24">
        <AgentsHubTabs active="multi-agent" />
        <GravitrePageHeader
          title="Multi-Agent Run"
          description="Coordinate multiple agents on parallel subtasks, then merge their results into one recommendation."
          icon={<Network className="h-5 w-5" />}
          className="border-0 px-0"
          actions={
            <>
              {selectedRun ? <AskGravitreSummonButton label="Review coordinated work" prompt="Review the selected multi-agent run’s reported contributions, disagreements and final recommendation." /> : null}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void mutate()}
                disabled={isValidating || !orgId}
                className="min-h-11"
              >
                <RefreshCw
                  className={cn(
                    "mr-1 h-4 w-4",
                    isValidating && "animate-spin motion-reduce:animate-none",
                  )}
                />
                Refresh
              </Button>
              <Button
                size="sm"
                onClick={() => setStartOpen(true)}
                className="min-h-11 gap-1"
                disabled={!orgId}
              >
                <Plus className="h-4 w-4" />
                Start multi-agent run
              </Button>
            </>
          }
        />

        <MultiAgentRunOverview
          activeRuns={data ? stats.active : null}
          completedRuns={data ? stats.completed : null}
          totalRuns={data ? stats.total : null}
        />

        <section className="grid max-w-lg grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
          <GravitreMetric
            label="Active"
            hint="In the latest 30 runs"
            value={data ? stats.active : "Not reported"}
          />
          <GravitreMetric
            label="Completed"
            hint="In the latest 30 runs"
            value={data ? stats.completed : "Not reported"}
          />
          <GravitreMetric
            label="Recent runs"
            value={data ? stats.total : "Not reported"}
          />
        </section>

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
        {!orgId ? (
          <p className="px-1 text-sm text-muted-foreground">
            {orgError ? "Run history is unavailable." : "Loading workspace…"}
          </p>
        ) : (
          <div
            className={cn(
              "grid gap-6",
              selectedId && "lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]",
            )}
          >
            <section className="space-y-2">
              <h2 className={TYPE.eyebrow}>Recent runs</h2>
              {isLoading && runs.length === 0 ? (
                <div className="rounded-xl border border-border/70 bg-card/40 px-6 py-10 text-center">
                  <RefreshCw className="mx-auto mb-3 h-5 w-5 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Loading runs…</p>
                </div>
              ) : runs.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/80 bg-gradient-to-b from-card/60 to-card/20 p-8 text-center">
                  <SwarmConvergenceDiagram variant="hero" className="mb-5" />
                  <p className="text-sm font-medium text-foreground">
                    No multi-agent runs yet
                  </p>
                  <p className="mx-auto mt-1 mb-4 max-w-sm text-xs text-muted-foreground">
                    Split one objective across parallel agents, then merge their
                    work into a single council recommendation.
                  </p>
                  <Button
                    size="sm"
                    className="min-h-11"
                    onClick={() => setStartOpen(true)}
                  >
                    Start your first run
                  </Button>
                </div>
              ) : (
                <ul className="space-y-2">
                  {runs.map((run, index) => (
                    <SwarmRunRow
                      key={run.id}
                      run={run}
                      index={index}
                      selected={selectedId === run.id}
                      onSelect={() =>
                        selectedId === run.id
                          ? handleCloseDetail()
                          : selectRun(run.id)
                      }
                    />
                  ))}
                </ul>
              )}
            </section>

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
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          Manage individual agents on{" "}
          <Link
            href={APP_ROUTES.agents}
            className="underline underline-offset-2 hover:text-foreground"
          >
            AI Team
          </Link>
          .
        </p>
      </div>

      <StartSwarmDialog
        open={startOpen}
        onOpenChange={setStartOpen}
        onStarted={handleStarted}
      />
    </div>
  )
}

function SwarmRunRow({
  run,
  index,
  selected,
  onSelect,
}: {
  run: AgentSwarmRun
  index: number
  selected: boolean
  onSelect: () => void
}) {
  const reduced = useReducedMotion()
  const preview = run.finalRecommendation
    ? formatSwarmReadableText(run.finalRecommendation, 120)
    : null

  return (
    <motion.li
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduced ? 0 : 0.18,
        delay: reduced ? 0 : Math.min(index, 5) * 0.02,
      }}
    >
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className={cn(
          "min-h-11 w-full border-b border-border px-3 py-4 text-left transition-colors",
          selected
            ? "border-l-2 border-l-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]"
            : "bg-transparent hover:bg-muted/30",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <SwarmRunStatusBadge status={run.status} />
              <span className="text-xs text-muted-foreground">
                {formatRelative(run.createdAt)}
              </span>
            </div>
            <p className="line-clamp-2 font-medium">{run.objective}</p>
            {preview ? (
              <div className="flex flex-wrap items-center gap-2">
                {isSwarmExecutionUnverified(run.executionVerified) ? (
                  <SwarmVerificationLabel compact />
                ) : null}
                <p className="line-clamp-1 text-xs text-muted-foreground">
                  {preview}
                </p>
              </div>
            ) : null}
          </div>
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        </div>
      </button>
    </motion.li>
  )
}
