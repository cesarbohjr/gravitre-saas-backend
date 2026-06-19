"use client"

import { Suspense, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { motion } from "framer-motion"
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
import type { AgentSwarmRun } from "@/types/api"
import { StartSwarmDialog } from "@/components/agent-swarm/start-swarm-dialog"
import { SwarmRunDetailPanel } from "@/components/agent-swarm/swarm-run-detail-panel"
import { SwarmRunStatusBadge } from "@/components/agent-swarm/swarm-status-badge"
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
  const [startOpen, setStartOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR("agent-swarm/runs", () => agentSwarmApi.list({ limit: 30 }), {
    refreshInterval: (latest) => {
      const runs = latest?.runs ?? []
      return runs.some((r) => ACTIVE.has(r.status)) ? 5000 : 0
    },
  })

  const runs = useMemo(() => data?.runs ?? [], [data])

  const stats = useMemo(() => {
    const active = runs.filter((r) => ACTIVE.has(r.status)).length
    const completed = runs.filter((r) => r.status === "completed").length
    return { active, completed, total: runs.length }
  }, [runs])

  function handleStarted(id: string) {
    void mutate()
    setSelectedId(id)
  }

  return (
    <div className="relative min-h-full">
      <GridPattern className="opacity-[0.35]" />
      <div className="relative z-10 mx-auto max-w-6xl p-4 sm:p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/20 to-blue-500/20 ring-1 ring-white/10">
              <Network className="h-5 w-5 text-violet-500" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Agent swarm</h1>
              <p className="text-sm text-muted-foreground max-w-xl">
                Coordinate multiple agents on parallel subtasks, then aggregate council recommendations.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void mutate()} disabled={isLoading}>
              <RefreshCw className={cn("h-4 w-4 mr-1", isLoading && "animate-spin")} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setStartOpen(true)} className="gap-1">
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
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Failed to load swarm runs.
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
            <section className="space-y-2">
              <h2 className="text-sm font-medium text-muted-foreground px-1">Recent runs</h2>
              {isLoading && runs.length === 0 ? (
                <p className="text-sm text-muted-foreground px-1">Loading runs…</p>
              ) : runs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border p-8 text-center space-y-3">
                  <Network className="h-10 w-10 mx-auto text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">No swarm runs yet.</p>
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
                      onSelect={() => setSelectedId(run.id)}
                    />
                  ))}
                </ul>
              )}
            </section>

            {selectedId ? (
              <SwarmRunDetailPanel
                swarmRunId={selectedId}
                onClose={() => setSelectedId(null)}
                onMutateList={() => void mutate()}
              />
            ) : (
              <div className="hidden lg:flex rounded-xl border border-dashed border-border items-center justify-center p-8 text-sm text-muted-foreground text-center">
                Select a run to view subtasks, aggregate results, or cancel in-flight work.
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
            ? "border-violet-500/40 bg-violet-500/5"
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
            {run.finalRecommendation ? (
              <p className="text-xs text-muted-foreground line-clamp-1">{run.finalRecommendation}</p>
            ) : null}
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground mt-1" />
        </div>
      </button>
    </motion.li>
  )
}
