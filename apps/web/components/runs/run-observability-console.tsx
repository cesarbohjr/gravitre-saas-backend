"use client"

import useSWR from "swr"
import Link from "next/link"
import { fetcher } from "@/lib/fetcher"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Activity,
  ArrowRightLeft,
  Brain,
  Clock,
  Coins,
  Gauge,
  MessageSquare,
  ShieldCheck,
  Wrench,
} from "lucide-react"

export type RunObservabilityDto = {
  runId: string
  intent?: string | null
  modelUsed?: string | null
  conversationId?: string | null
  contextSources: string[]
  ragQueries: Array<{ turnId?: string; knowledgeSummary?: unknown; at?: string }>
  toolsCalled: Array<{
    action?: string
    tool?: string
    connectorId?: string
    status?: string
    at?: string
  }>
  agentHandoffs: Array<{
    action?: string
    fromAgentId?: string
    toAgentId?: string
    at?: string
  }>
  actionsTaken: Array<{ action?: string; at?: string; actorId?: string }>
  approvalsRequired: boolean
  confidence?: number | null
  latencyMs?: number | null
  costUsd?: number | null
  finalResult: { status?: string; errorMessage?: string; completedAt?: string }
  replay: Array<Record<string, unknown>>
  sources: Record<string, string>
  auditEventCount: number
  cognitiveTurns: unknown[]
  outcomeEvents: unknown[]
}

function formatMs(ms?: number | null): string {
  if (ms == null || Number.isNaN(ms)) return "—"
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Clock
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-1 truncate text-sm font-medium text-foreground">{value}</p>
    </div>
  )
}

export function RunObservabilityConsole({ runId }: { runId: string }) {
  const { data, error, isLoading } = useSWR<RunObservabilityDto>(
    runId ? `/api/runs/${runId}/observability` : null,
    fetcher,
    { revalidateOnFocus: false },
  )

  if (isLoading) {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-card p-4">
        <Skeleton className="h-5 w-48" />
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        Observability join unavailable for this run.
      </div>
    )
  }

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Run observability</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Joined view over existing audit, cognitive, outcome, and step stores — no private
            chain-of-thought.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className="text-[10px]">
            {data.auditEventCount} audit events
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {data.cognitiveTurns.length} cognitive turns
          </Badge>
          {data.approvalsRequired ? (
            <Badge variant="outline" className="gap-1 text-[10px]">
              <ShieldCheck className="h-3 w-3" />
              Approvals required
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat icon={Brain} label="Intent" value={data.intent || "—"} />
        <Stat icon={MessageSquare} label="Model" value={data.modelUsed || "—"} />
        <Stat icon={Clock} label="Latency" value={formatMs(data.latencyMs)} />
        <Stat
          icon={Coins}
          label="Cost"
          value={data.costUsd != null ? `$${Number(data.costUsd).toFixed(4)}` : "—"}
        />
        <Stat
          icon={Gauge}
          label="Confidence"
          value={data.confidence != null ? String(data.confidence) : "—"}
        />
        <Stat icon={Activity} label="Result" value={data.finalResult.status || "—"} />
        <Stat icon={Wrench} label="Tools" value={String(data.toolsCalled.length)} />
        <Stat
          icon={ArrowRightLeft}
          label="Handoffs"
          value={String(data.agentHandoffs.length)}
        />
      </div>

      {data.conversationId ? (
        <p className="text-xs text-muted-foreground">
          Conversation{" "}
          <Link className="text-foreground underline-offset-2 hover:underline" href={`/ai?c=${data.conversationId}`}>
            {data.conversationId.slice(0, 8)}…
          </Link>
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Context sources
          </h3>
          {data.contextSources.length === 0 ? (
            <p className="text-xs text-muted-foreground">None recorded</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {data.contextSources.map((src) => (
                <li
                  key={src}
                  className="rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-foreground"
                >
                  {src}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Tools called
          </h3>
          {data.toolsCalled.length === 0 ? (
            <p className="text-xs text-muted-foreground">No tool.invoke.* audits for this run</p>
          ) : (
            <ul className="space-y-1">
              {data.toolsCalled.slice(0, 12).map((tool, idx) => (
                <li
                  key={`${tool.tool}-${idx}`}
                  className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1 text-xs"
                >
                  <span className="truncate font-medium">{tool.tool || tool.action || "tool"}</span>
                  <span
                    className={cn(
                      "shrink-0 text-[10px] uppercase",
                      tool.status === "failed" ? "text-destructive" : "text-muted-foreground",
                    )}
                  >
                    {tool.status || "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Replay (public path)
        </h3>
        {data.replay.length === 0 ? (
          <p className="text-xs text-muted-foreground">No replay events</p>
        ) : (
          <ol className="space-y-1">
            {data.replay.slice(0, 24).map((event, idx) => {
              const kind = String(event.kind || "event")
              const label =
                kind === "step"
                  ? String(event.name || "Step")
                  : kind === "tool"
                    ? String(event.tool || event.action || "Tool")
                    : kind === "handoff"
                      ? `Handoff ${event.fromAgentId || "?"} → ${event.toAgentId || "?"}`
                      : kind
              return (
                <li
                  key={`${kind}-${idx}`}
                  className="flex items-center gap-2 rounded-md border border-border/70 px-2 py-1 text-xs"
                >
                  <span className="w-16 shrink-0 text-[10px] uppercase text-muted-foreground">
                    {kind}
                  </span>
                  <span className="truncate text-foreground">{label}</span>
                  {event.status ? (
                    <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                      {String(event.status)}
                    </span>
                  ) : null}
                </li>
              )
            })}
          </ol>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground">
        Sources: {Object.entries(data.sources).map(([k, v]) => `${k}=${v}`).join(" · ")}
      </p>
    </section>
  )
}
