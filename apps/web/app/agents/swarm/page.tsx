"use client"

import { Suspense, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { motion } from "framer-motion"
import { toast } from "sonner"
import {
  ChevronRight,
  Network,
  Plus,
  RefreshCw,
} from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { GridPattern, AnimatedCounter } from "@/components/gravitre/premium-effects"
import { agentSwarmApi } from "@/lib/api"
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
  if (!iso) return "—"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

export default function AgentSwarmPage() {
  return (
    <AppShell title="Agent Swarm">
      <Suspense fallback={null}>
        <AgentSwarmContent />
      </Suspense>
    </AppShell>
  )
}

function AgentSwarmContent() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [orgId, setOrgId] = useState<string | null>(null)
  const [startOpen, setStartOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(() => searchParams.get("runId"))
  const prevStatusRef = useRef<Map<string, string>>(new Map())
  const notifiedRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (user) void ensureSelectedOrg(true).then(setOrgId)
  }, [user])

  useEffect(() => {
    const runId = searchParams.get("runId")
    if (runId) setSelectedId(runId)
  }, [searchParams])

  const swrKey = orgId ? `agent-swarm/runs:${orgId}` : null
  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR(swrKey, () => agentSwarmApi.list({ limit: 30 }), {
    refreshInterval: (latest) => {
      const runs = latest?.runs ?? []
      return runs.some((r) => ACTIVE.has(r.status)) ? 5000 : 0
    },
  })

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
        toast.success("Swarm complete", {
          description: summary || run.objective,
          action: {
            label: "View results",
            onClick: () => selectRun(run.id),
          },
        })
      }
    }
  }, [runs])

  const stats = useMemo(() => {
    const active = runs.filter((r) => ACTIVE.has(r.status)).length
    const completed = runs.filter((r) => r.status === "completed").length
    return { active, completed, total: runs.length }
  }, [runs])

  function selectRun(id: string) {
    setSelectedId(id)
    router.replace(`/agents/swarm?runId=${id}`, { scroll: false })
  }

  function handleStarted(id: string) {
    void mutate()
    selectRun(id)
  }

  function handleCloseDetail() {
    setSelectedId(null)
    router.replace("/agents/swarm", { scroll: false })
  }

  return (
    <div className="relative min-h-full">
      <GridPattern className="opacity-[0.35]" />
      <div className="relative z-10 mx-auto max-w-6xl p-4 sm:p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-border">
              <Network className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Agent swarm</h1>
              <p className="text-sm text-muted-foreground max-w-xl">
                Coordinate multiple agents on parallel subtasks, then aggregate council recommendations.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void mutate()} disabled={isLoading || !orgId}>
              <RefreshCw className={cn("h-4 w-4 mr-1", isLoading && "animate-spin")} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setStartOpen(true)} className="gap-1" disabled={!orgId}>
              <Plus className="h-4 w-4" />
              Start swarm
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 max-w-md">
          <StatTile label="Active" value={stats.active} />
          <StatTile label="Completed" value={stats.completed} />
          <StatTile label="Total runs" value={stats.total} />
        </div>

        {error ? (
          <WorkSectionErrorCard
            title="Couldn't load swarm runs"
            message="We couldn't fetch your swarm history. Check your connection and try again."
            error={error}
            onRetry={() => void mutate()}
          />
        ) : !orgId ? (
          <p className="text-sm text-muted-foreground px-1">Loading organization…</p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
            <section className="space-y-2">
              <h2 className="text-sm font-medium text-muted-foreground px-1">Recent runs</h2>
              {isLoading && runs.length === 0 ? (
                <p className="text-sm text-muted-foreground px-1">Loading runs…</p>
              ) : runs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border p-8 text-center">
                  <SwarmConvergenceDiagram variant="hero" className="mb-5" />
                  <p className="text-sm font-medium text-foreground">No swarm runs yet</p>
                  <p className="mx-auto mt-1 mb-4 max-w-sm text-xs text-muted-foreground">
                    A swarm splits one objective across parallel agents, then merges their work into a single council recommendation.
                  </p>
                  <Button size="sm" onClick={() => setStartOpen(true)}>
                    Start your first swarm
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
                      onSelect={() => selectRun(run.id)}
                    />
                  ))}
                </ul>
              )}
            </section>

            {selectedId ? (
              <SwarmRunDetailPanel
                swarmRunId={selectedId}
                onClose={handleCloseDetail}
                onMutateList={() => void mutate()}
              />
            ) : (
              <div className="hidden lg:flex flex-col rounded-xl border border-dashed border-border items-center justify-center gap-4 p-8 text-center">
                <SwarmConvergenceDiagram variant="panel" />
                <p className="text-sm text-muted-foreground">
                  Select a run to view subtasks, aggregate results, or cancel in-flight work.
                </p>
              </div>
            )}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          Manage individual agents on{" "}
          <Link href="/agents" className="underline underline-offset-2 hover:text-foreground">
            AI Team
          </Link>
          .
        </p>
      </div>

      <StartSwarmDialog open={startOpen} onOpenChange={setStartOpen} onStarted={handleStarted} />
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border/70 bg-card/50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">
        <AnimatedCounter value={value} duration={0.6} />
      </p>
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
  const preview = run.finalRecommendation
    ? formatSwarmReadableText(run.finalRecommendation, 120)
    : null

  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
    >
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "w-full text-left rounded-xl border p-4 transition-colors",
          selected
            ? "border-primary/40 bg-primary/5"
            : "border-border/70 bg-card/40 hover:bg-muted/30",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <SwarmRunStatusBadge status={run.status} />
              <span className="text-xs text-muted-foreground">{formatRelative(run.createdAt)}</span>
            </div>
            <p className="font-medium line-clamp-2">{run.objective}</p>
            {preview ? (
              <div className="flex items-center gap-2 flex-wrap">
                {isSwarmExecutionUnverified(run.executionVerified) ? (
                  <SwarmVerificationLabel compact />
                ) : null}
                <p className="text-xs text-muted-foreground line-clamp-1">{preview}</p>
              </div>
            ) : null}
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground mt-1" />
        </div>
      </button>
    </motion.li>
  )
}
