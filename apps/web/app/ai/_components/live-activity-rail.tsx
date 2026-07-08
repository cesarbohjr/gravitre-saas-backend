"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { useAuth } from "@/lib/auth-context"
import { runsApi, activityApi } from "@/lib/api"
import { assistantApi } from "@/lib/api"
import { getSelectedOrgFromStorage, ensureSelectedOrg } from "@/lib/org-context"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import type { Run, RunStatus, ActivityEvent } from "@/types/api"
import { Activity, CheckCircle2, ExternalLink, Loader2, PlayCircle } from "lucide-react"
import { AiExecuteResults } from "./ai-execute-results"
import type { AgentJob } from "@/hooks/use-async-job"
import type { InlineExecutePlan } from "@/lib/ai-inline-execute"
import type { LayoutColumn, ResultBlockId } from "./draggable-result-stack"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import { MesonPagePanel } from "@/components/gravitre/meson-page-panel"
import { routeMesonSuggestion } from "@/lib/meson-page-context"

function relativeTime(value?: string): string {
  if (!value) return ""
  const ts = new Date(value).getTime()
  if (Number.isNaN(ts)) return ""
  const diff = Math.max(0, Date.now() - ts)
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "now"
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.floor(hrs / 24)}d`
}

function isRunning(status: RunStatus): boolean {
  return status === "running" || status === "pending" || status === "approved"
}

function statusTone(status: RunStatus): string {
  if (status === "completed") return "text-success"
  if (status === "failed" || status === "rejected") return "text-destructive"
  if (isRunning(status)) return "text-info"
  return "text-muted-foreground"
}

function runName(run: Run): string {
  return run.workflow_name ?? run.workflowName ?? run.workflow_id ?? run.id
}

type RecentFeedItem =
  | { kind: "run"; id: string; title: string; status: RunStatus; href: string; at?: string }
  | { kind: "connector"; id: string; title: string; body: string; href: string; integration?: string; at?: string }

function mergeRecentFeed(runs: Run[], connectorEvents: ActivityEvent[]): RecentFeedItem[] {
  const runItems: RecentFeedItem[] = runs
    .filter((run) => !isRunning(run.status))
    .slice(0, 4)
    .map((run) => ({
      kind: "run" as const,
      id: run.id,
      title: runName(run),
      status: run.status,
      href: `/runs/${run.id}`,
      at: run.completed_at ?? run.started_at ?? run.created_at,
    }))
  const connectorItems: RecentFeedItem[] = connectorEvents.slice(0, 6).map((event) => ({
    kind: "connector" as const,
    id: event.id,
    title: event.title,
    body: event.body,
    href: event.url || "/ai",
    integration: event.integration,
    at: event.created_at,
  }))
  return [...runItems, ...connectorItems]
    .sort((a, b) => new Date(b.at ?? 0).getTime() - new Date(a.at ?? 0).getTime())
    .slice(0, 6)
}

/** Right-hand rail summarizing live org activity for the unified AI surface. */
export function LiveActivityRail({
  advisorBrief = null,
  layoutPlan = null,
  layoutJob = null,
  layoutProcessing = false,
  layoutError = null,
  layoutBlockOrder = [],
  layoutEnabledBlocks = [],
  layoutBlockColumns = {},
  onReorderLayoutBlocks,
  onMoveLayoutBlockToColumn,
}: {
  advisorBrief?: AdvisorBrief | null
  layoutPlan?: InlineExecutePlan | null
  layoutJob?: AgentJob | null
  layoutProcessing?: boolean
  layoutError?: string | null
  layoutBlockOrder?: ResultBlockId[]
  layoutEnabledBlocks?: ResultBlockId[]
  layoutBlockColumns?: Partial<Record<ResultBlockId, LayoutColumn>>
  onReorderLayoutBlocks?: (next: ResultBlockId[]) => void
  onMoveLayoutBlockToColumn?: (blockId: ResultBlockId, target: LayoutColumn) => void
} = {}) {
  const { user } = useAuth()
  const router = useRouter()
  const [orgId, setOrgId] = useState<string | null>(() =>
    typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id ?? null : null,
  )

  useEffect(() => {
    if (!user) {
      setOrgId(null)
      return
    }
    void ensureSelectedOrg(false).then((resolved) => setOrgId(resolved))
  }, [user])

  const { data: runsData } = useSWR(
    user && orgId ? ["ai-rail-runs", orgId] : null,
    () => runsApi.list({ limit: 8 }),
    { revalidateOnFocus: false, refreshInterval: 20_000 },
  )
  const { data: activityData } = useSWR(
    user && orgId ? ["ai-rail-activity", orgId] : null,
    () => activityApi.recent({ limit: 8, source: "connector_write" }),
    { revalidateOnFocus: false, refreshInterval: 20_000 },
  )
  const {
    data: orgContext,
    error: orgContextError,
    mutate: refreshOrgContext,
    isLoading: orgContextLoading,
  } = useSWR(
    user && orgId ? ["ai-rail-org-context", orgId] : null,
    () => assistantApi.orgContext(),
    { revalidateOnFocus: false },
  )

  const runs = runsData?.runs ?? []
  const active = runs.filter((r) => isRunning(r.status))
  const inProgress = active.slice(0, 2)
  const recent = mergeRecentFeed(runs, activityData?.events ?? [])
  const connectorCount = orgContext?.counts.connectors ?? 0
  const systemsHealthy = connectorCount > 0
  const systemsUnavailable = Boolean(orgContextError)
  const systemsDisplay = systemsUnavailable ? "—" : systemsHealthy ? String(connectorCount) : "0"
  const systemsCaption = orgContextLoading
    ? "Checking status…"
    : systemsUnavailable
      ? "Status unavailable"
      : "Systems healthy"

  return (
    <div className="flex h-full max-h-full w-80 flex-col overflow-y-auto">
      <div className="flex flex-col gap-6 p-5">
        <MesonPagePanel
          page="ai-chat"
          compact
          advisorBrief={advisorBrief}
          onSuggestionClick={(suggestion) =>
            routeMesonSuggestion("/ai", suggestion, (href) => router.push(href))
          }
        />

        <div className="border-t border-emerald-500/10 pt-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500/70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <h2 className="text-sm font-semibold text-foreground">Live activity</h2>
        </div>
        </div>

        {/* Summary tiles */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/8 p-3">
            <p
              className={cn(
                "text-2xl font-semibold tabular-nums",
                systemsUnavailable
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-emerald-600 dark:text-emerald-400",
              )}
            >
              {systemsDisplay}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">{systemsCaption}</p>
            {systemsUnavailable ? (
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 h-7 px-2 text-xs"
                onClick={() => void refreshOrgContext()}
              >
                Retry
              </Button>
            ) : null}
          </div>
          <div className="rounded-xl border border-blue-500/20 bg-blue-500/8 p-3">
            <p className="text-2xl font-semibold tabular-nums text-blue-600 dark:text-blue-400">{active.length}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Active runs</p>
          </div>
        </div>

        {/* In progress */}
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">In progress</p>
          {inProgress.length > 0 ? (
            <ul className="space-y-2">
              {inProgress.map((run) => (
                <li key={run.id}>
                  <Link
                    href={`/runs/${run.id}`}
                    className="block rounded-xl border border-blue-500/15 bg-background/80 p-3 transition-all hover:border-blue-500/35 hover:bg-blue-500/5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{runName(run)}</span>
                      <span className="text-[11px] text-muted-foreground">{relativeTime(run.started_at ?? run.created_at)}</span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin text-info" aria-hidden />
                      <span className="text-xs capitalize text-info">{run.status}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-dashed border-border bg-background/60 p-3 text-xs text-muted-foreground">
              Nothing running right now.
            </p>
          )}
        </div>

        {/* Recent */}
        {recent.length > 0 ? (
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Recent</p>
            <ul className="space-y-1">
              {recent.map((item) => (
                <motion.li key={`${item.kind}-${item.id}`} whileHover={{ x: 2 }}>
                  <Link
                    href={item.href}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-secondary/60"
                  >
                    {item.kind === "connector" ? (
                      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-violet-500" aria-hidden />
                    ) : item.status === "completed" ? (
                      <CheckCircle2 className={cn("h-3.5 w-3.5 shrink-0", statusTone(item.status))} aria-hidden />
                    ) : (
                      <PlayCircle className={cn("h-3.5 w-3.5 shrink-0", statusTone(item.status))} aria-hidden />
                    )}
                    <span className="min-w-0 flex-1 truncate text-foreground">
                      {item.kind === "connector" && item.integration
                        ? `${item.integration}: ${item.title}`
                        : item.title}
                    </span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">
                      {relativeTime(item.at)}
                    </span>
                  </Link>
                </motion.li>
              ))}
            </ul>
          </div>
        ) : null}

        {layoutEnabledBlocks.length > 0 ? (
          <div className="border-t border-border/70 pt-4">
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Workspace panels
            </p>
            <AiExecuteResults
              plan={layoutPlan}
              job={layoutJob}
              isProcessing={layoutProcessing}
              error={layoutError}
              blockOrder={layoutBlockOrder}
              enabledBlocks={layoutEnabledBlocks}
              onReorderBlocks={onReorderLayoutBlocks}
              blockColumns={layoutBlockColumns}
              onMoveBlockToColumn={onMoveLayoutBlockToColumn}
              column="rail"
              compact
            />
          </div>
        ) : null}

        <Link
          href="/runs"
          className="mt-auto inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:underline dark:text-emerald-400"
        >
          <Activity className="h-3.5 w-3.5" aria-hidden />
          View all runs
        </Link>
      </div>
    </div>
  )
}
