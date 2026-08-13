"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { intelligenceApi } from "@/lib/api"
import { stageLabel, surfaceLabel } from "@/lib/learning-ui-copy"
import { Brain, Clock, Path, CaretDown, CaretUp } from "@phosphor-icons/react"
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

const PAGE_SIZE = 15

function StagesTimeline({ stages }: { stages: TraceRow["stages"] }) {
  const list = stages ?? []
  if (list.length === 0) {
    return <span className="text-xs text-muted-foreground">No steps recorded</span>
  }
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Turn steps">
      {list.map((stage, idx) => {
        const name = stageLabel(stage.stage)
        const ok = stage.ok !== false
        return (
          <li key={`${name}-${idx}`} className="flex items-center gap-1.5">
            {idx > 0 ? (
              <span className="text-muted-foreground/50" aria-hidden>
                →
              </span>
            ) : null}
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

function SummaryBlock({ title, value }: { title: string; value: Record<string, unknown> }) {
  const [open, setOpen] = useState(false)
  const keys = Object.keys(value)
  const preview = keys
    .slice(0, 4)
    .map((k) => `${k.replace(/_/g, " ")}: ${String(value[k]).slice(0, 40)}`)
    .join(" · ")

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{title}</p>
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setOpen((v) => !v)}>
          {open ? (
            <>
              Hide details <CaretUp className="ml-1 h-3.5 w-3.5" aria-hidden />
            </>
          ) : (
            <>
              Technical details <CaretDown className="ml-1 h-3.5 w-3.5" aria-hidden />
            </>
          )}
        </Button>
      </div>
      {!open && preview ? <p className="mt-1 text-xs text-muted-foreground text-pretty">{preview}</p> : null}
      {open ? (
        <pre className="mt-1 overflow-x-auto rounded-lg border border-border/60 bg-secondary/30 p-3 text-[11px] leading-relaxed text-muted-foreground">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}

export function CognitiveTurnsTab({ enabled }: { enabled: boolean }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [surfaceFilter, setSurfaceFilter] = useState<string>("all")
  const [page, setPage] = useState(0)

  const { data, error, isLoading, mutate } = useSWR(
    enabled ? ["admin/intelligence/cognitive-turns"] : null,
    () => intelligenceApi.cognitiveTurns({ limit: 80 }),
    { revalidateOnFocus: false },
  )

  const traces = (data?.traces ?? []) as TraceRow[]
  const surfaces = useMemo(() => {
    const set = new Set<string>()
    for (const t of traces) {
      if (t.surface) set.add(String(t.surface))
    }
    return Array.from(set).sort()
  }, [traces])

  const filtered = useMemo(() => {
    if (surfaceFilter === "all") return traces
    return traces.filter((t) => String(t.surface ?? "") === surfaceFilter)
  }, [traces, surfaceFilter])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

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
          title="Recent turns"
          description="What happened on recent chat and agent turns — surface, timing, and step-by-step path."
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {traces.length === 0 ? (
            <div className="mt-2">
              <NotYetPopulated>
                No turns recorded yet. They appear when people chat or agents run in your organization.
              </NotYetPopulated>
            </div>
          ) : (
            <>
              <div className="mt-3 mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                <Select
                  value={surfaceFilter}
                  onValueChange={(v) => {
                    setSurfaceFilter(v)
                    setPage(0)
                  }}
                >
                  <SelectTrigger className="w-full sm:w-[12rem]" aria-label="Filter by surface">
                    <SelectValue placeholder="All surfaces" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All surfaces</SelectItem>
                    {surfaces.map((s) => (
                      <SelectItem key={s} value={s}>
                        {surfaceLabel(s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground sm:ml-auto tabular-nums">
                  {filtered.length} turn{filtered.length === 1 ? "" : "s"}
                </p>
              </div>
              {pageItems.length === 0 ? (
                <NotYetPopulated>No turns match this filter.</NotYetPopulated>
              ) : (
                <ul className="divide-y divide-border/60 rounded-xl border border-border/70">
                  {pageItems.map((trace) => {
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
                            {trace.surface ? (
                              <Badge variant="outline" className="text-[11px]">
                                {surfaceLabel(trace.surface)}
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
              {pageCount > 1 ? (
                <div className="mt-3 flex items-center justify-between gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={safePage <= 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    Page {safePage + 1} of {pageCount}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={safePage >= pageCount - 1}
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </SectionCard>

        <SectionCard
          title="Turn detail"
          description={selectedId ? "Steps and summaries for the selected turn." : "Select a turn to inspect."}
          icon={<Path className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {!selectedId ? (
            <p className="mt-2 text-sm text-muted-foreground">Select a turn from the list.</p>
          ) : detailLoading && !detail ? (
            <p className="mt-2 text-sm text-muted-foreground">Loading detail…</p>
          ) : detail ? (
            <div className="mt-3 space-y-4 text-sm">
              <dl className="grid gap-2 sm:grid-cols-2">
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Surface</dt>
                  <dd className="mt-0.5">{surfaceLabel(detail.surface)}</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">When</dt>
                  <dd className="mt-0.5">{formatTime(detail.created_at)}</dd>
                </div>
              </dl>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Steps</p>
                <div className="mt-2">
                  <StagesTimeline stages={detail.stages} />
                </div>
              </div>

              {detail.memory_summary ? (
                <SummaryBlock title="Memory used" value={detail.memory_summary} />
              ) : null}

              {detail.knowledge_summary ? (
                <SummaryBlock title="Knowledge used" value={detail.knowledge_summary} />
              ) : null}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">Turn not found.</p>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
