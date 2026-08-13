"use client"

import { useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { Brain, Clock, Path } from "@phosphor-icons/react"
import { formatTime, NotYetPopulated, SectionCard, TabStateGate } from "./shared"
import { cn } from "@/lib/utils"

type TraceRow = {
  turn_id?: string
  surface?: string
  stages?: Array<{ stage?: string; ok?: boolean; ms?: number; meta?: Record<string, unknown> }>
  created_at?: string
  memory_summary?: Record<string, unknown>
  knowledge_summary?: Record<string, unknown>
  conversation_id?: string | null
  user_id?: string | null
  [key: string]: unknown
}

function StagesTimeline({ stages }: { stages: TraceRow["stages"] }) {
  const list = stages ?? []
  if (list.length === 0) {
    return <span className="text-xs text-muted-foreground">No stages</span>
  }
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Stage timeline">
      {list.map((stage, idx) => {
        const name = String(stage.stage ?? "?")
        const ok = stage.ok !== false
        return (
          <li key={`${name}-${idx}`} className="flex items-center gap-1.5">
            {idx > 0 ? <span className="text-muted-foreground/50" aria-hidden>→</span> : null}
            <span
              className={cn(
                "rounded-md border px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
                ok
                  ? "border-border/70 bg-secondary/50 text-foreground"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-700",
              )}
              title={typeof stage.ms === "number" ? `${stage.ms} ms` : undefined}
            >
              {name}
              {typeof stage.ms === "number" ? (
                <span className="ml-1 text-muted-foreground">{Math.round(stage.ms)}ms</span>
              ) : null}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function CognitiveTurnsTab({ enabled }: { enabled: boolean }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR(
    enabled ? ["admin/intelligence/cognitive-turns"] : null,
    () => intelligenceApi.cognitiveTurns({ limit: 50 }),
    { revalidateOnFocus: false },
  )

  const traces = (data?.traces ?? []) as TraceRow[]
  const selected = traces.find((t) => t.turn_id === selectedId) ?? null

  const { data: detailData, isLoading: detailLoading } = useSWR(
    enabled && selectedId ? ["admin/intelligence/cognitive-turn", selectedId] : null,
    () => intelligenceApi.cognitiveTurn(selectedId!),
    { revalidateOnFocus: false },
  )
  const detail = (detailData?.trace ?? selected) as TraceRow | null

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <SectionCard
          title="Cognitive turns"
          description="Org-scoped pre-ACT traces — turn id, surface, stage timeline, and created time."
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {traces.length === 0 ? (
            <div className="mt-2">
              <NotYetPopulated>
                No cognitive turn traces yet. Traces appear when the kernel runs on a chat or agent turn.
              </NotYetPopulated>
            </div>
          ) : (
            <ul className="mt-3 divide-y divide-border/60 rounded-xl border border-border/70">
              {traces.map((trace) => {
                const id = String(trace.turn_id ?? "")
                const active = id && id === selectedId
                return (
                  <li key={id || String(trace.created_at)}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(id || null)}
                      className={cn(
                        "flex w-full flex-col gap-2 px-4 py-3 text-left transition-colors",
                        active ? "bg-secondary/50" : "hover:bg-secondary/30",
                      )}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="text-xs font-medium text-foreground">{id.slice(0, 8) || "—"}</code>
                        {trace.surface ? (
                          <Badge variant="outline" className="text-[11px]">
                            {trace.surface}
                          </Badge>
                        ) : null}
                        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                          <Clock className="h-3 w-3" weight="bold" aria-hidden />
                          {formatTime(trace.created_at)}
                        </span>
                      </div>
                      <StagesTimeline stages={trace.stages} />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          title="Turn detail"
          description={
            selectedId
              ? `Selected turn ${selectedId.slice(0, 8)}…`
              : "Select a turn to inspect stages and summaries."
          }
          icon={<Path className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {!selectedId ? (
            <p className="mt-2 text-sm text-muted-foreground">No turn selected.</p>
          ) : detailLoading && !detail ? (
            <p className="mt-2 text-sm text-muted-foreground">Loading detail…</p>
          ) : detail ? (
            <div className="mt-3 space-y-4 text-sm">
              <dl className="grid gap-2 sm:grid-cols-2">
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Turn id</dt>
                  <dd className="mt-0.5 break-all font-mono text-xs">{String(detail.turn_id ?? "—")}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Surface</dt>
                  <dd className="mt-0.5">{String(detail.surface ?? "—")}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Created</dt>
                  <dd className="mt-0.5">{formatTime(detail.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Conversation</dt>
                  <dd className="mt-0.5 break-all font-mono text-xs">
                    {String(detail.conversation_id ?? "—")}
                  </dd>
                </div>
              </dl>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Stages</p>
                <div className="mt-2">
                  <StagesTimeline stages={detail.stages} />
                </div>
              </div>

              {detail.memory_summary ? (
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Memory summary</p>
                  <pre className="mt-1 overflow-x-auto rounded-lg border border-border/60 bg-secondary/30 p-3 text-[11px] leading-relaxed text-muted-foreground">
                    {JSON.stringify(detail.memory_summary, null, 2)}
                  </pre>
                </div>
              ) : null}

              {detail.knowledge_summary ? (
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Knowledge summary</p>
                  <pre className="mt-1 overflow-x-auto rounded-lg border border-border/60 bg-secondary/30 p-3 text-[11px] leading-relaxed text-muted-foreground">
                    {JSON.stringify(detail.knowledge_summary, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">Trace not found.</p>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
