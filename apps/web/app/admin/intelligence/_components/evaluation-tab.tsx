"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { intelligenceApi } from "@/lib/api"
import { surfaceLabel } from "@/lib/learning-ui-copy"
import { Gauge, ListChecks, Clock } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, ScoreBar, scoreColor, formatScore, formatTime } from "./shared"
import { LearningToRankCard } from "./learning-to-rank-card"
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"

const PAGE_SIZE = 12

function MetricPill({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-md border border-border/60 bg-secondary/40 px-2 py-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className={cn("text-xs font-semibold tabular-nums", tone ?? "text-foreground")}>{value}</span>
    </span>
  )
}

export function EvaluationTab({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? ["admin/intelligence/evaluations"] : null,
    () => intelligenceApi.evaluations({ limit: 80 }),
    { revalidateOnFocus: false },
  )

  const [query, setQuery] = useState("")
  const [feedbackFilter, setFeedbackFilter] = useState<"all" | "helpful" | "not_helpful" | "none">("all")
  const [page, setPage] = useState(0)

  const composite = data?.summary.avgCompositeScore ?? null
  const compositeColor = composite != null ? scoreColor(composite) : null

  const components = useMemo(() => {
    if (!data) return []
    const { summary, compositeScoreWeights, evaluations } = data
    const feedbackTotal = summary.helpfulCount + summary.notHelpfulCount
    const feedbackScore = feedbackTotal > 0 ? summary.helpfulCount / feedbackTotal : null
    const reliabilityValues = evaluations
      .map((e) => e.chunkOutcomeSummary?.avgReliability)
      .filter((v): v is number => typeof v === "number")
    const reliabilityScore =
      reliabilityValues.length > 0
        ? reliabilityValues.reduce((a, b) => a + b, 0) / reliabilityValues.length
        : null
    return [
      {
        key: "rag",
        label: "Search & grounding",
        score: summary.avgRagQualityScore,
        weight: compositeScoreWeights.ragQualityScore,
      },
      {
        key: "feedback",
        label: "User feedback",
        score: feedbackScore,
        weight: compositeScoreWeights.userFeedback,
      },
      {
        key: "reliability",
        label: "Source reliability",
        score: reliabilityScore,
        weight: compositeScoreWeights.chunkReliabilityAvg,
      },
    ]
  }, [data])

  const samples = data?.evaluations ?? []

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return samples.filter((s) => {
      if (feedbackFilter === "helpful" && s.userFeedback !== "helpful") return false
      if (feedbackFilter === "not_helpful" && s.userFeedback !== "not_helpful") return false
      if (feedbackFilter === "none" && s.userFeedback) return false
      if (!q) return true
      const hay = `${s.surface ?? ""} ${s.feedbackReason ?? ""} ${s.messageId ?? ""}`.toLowerCase()
      return hay.includes(q)
    })
  }, [samples, feedbackFilter, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-6">
        <SectionCard
          title={SURFACE_COPY.learningAdmin.evaluationQualityTitle}
          description={SURFACE_COPY.learningAdmin.evaluationQualityHint}
          icon={<Gauge className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[auto_1fr] md:items-center">
            <div className="relative flex min-w-[10rem] flex-col items-center justify-center overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-b from-secondary/60 to-background px-8 py-6 text-center">
              <span
                aria-hidden
                className={cn(
                  "pointer-events-none absolute -top-8 left-1/2 h-24 w-24 -translate-x-1/2 rounded-full opacity-25 blur-2xl",
                  composite != null && composite >= 0.75
                    ? "bg-emerald-500"
                    : composite != null && composite >= 0.5
                      ? "bg-amber-500"
                      : "bg-rose-500",
                )}
              />
              <span className="relative text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Overall quality
              </span>
              <motion.span
                key={formatScore(composite)}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                className={cn(
                  "relative mt-1 text-5xl font-semibold tabular-nums",
                  compositeColor?.text ?? "text-muted-foreground",
                )}
              >
                {formatScore(composite)}
              </motion.span>
              <span className="relative mt-0.5 text-xs text-muted-foreground">out of 1.00</span>
              {data ? (
                <span className="relative mt-2 rounded-full bg-secondary px-2 py-0.5 text-xs text-muted-foreground tabular-nums">
                  {data.summary.totalEvaluations} scored answer
                  {data.summary.totalEvaluations === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>

            <div className="space-y-4">
              {components.map((c) => (
                <ScoreBar key={c.key} label={c.label} score={c.score ?? 0} weight={c.weight} />
              ))}
            </div>
          </div>

          {composite == null ? (
            <div className="mt-4">
              <NotYetPopulated>
                No answers have been scored yet. Quality scores appear as people chat and leave feedback.
              </NotYetPopulated>
            </div>
          ) : null}
        </SectionCard>

        {data ? <LearningToRankCard status={data.retrievalRanker} delay={0.06} /> : null}

        <SectionCard
          title={SURFACE_COPY.learningAdmin.scoredResponsesTitle}
          description="Individual answers with quality scores and optional user ratings."
          icon={<ListChecks className="h-5 w-5" weight="duotone" aria-hidden />}
          delay={0.12}
        >
          {samples.length > 0 ? (
            <>
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Input
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setPage(0)
                  }}
                  placeholder="Filter by surface or feedback…"
                  className="sm:max-w-xs"
                  aria-label="Filter scored answers"
                />
                <Select
                  value={feedbackFilter}
                  onValueChange={(v) => {
                    setFeedbackFilter(v as typeof feedbackFilter)
                    setPage(0)
                  }}
                >
                  <SelectTrigger className="w-full sm:w-[11rem]" aria-label="Filter by rating">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All ratings</SelectItem>
                    <SelectItem value="helpful">Rated helpful</SelectItem>
                    <SelectItem value="not_helpful">Rated not helpful</SelectItem>
                    <SelectItem value="none">No rating yet</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground sm:ml-auto tabular-nums">
                  {filtered.length} of {samples.length}
                </p>
              </div>
              {pageItems.length > 0 ? (
                <ul className="divide-y divide-border">
                  {pageItems.map((s) => {
                    const { text } = scoreColor(s.compositeScore ?? 0)
                    return (
                      <li
                        key={s.id}
                        className="-mx-2 rounded-lg px-2 py-3 transition-colors first:pt-0 last:pb-0 hover:bg-secondary/50"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <Badge variant="outline">{surfaceLabel(s.surface)}</Badge>
                            {s.userFeedback ? (
                              <Badge
                                variant="secondary"
                                className={
                                  s.userFeedback === "helpful"
                                    ? "border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/40 dark:text-emerald-300"
                                    : "border-rose-300 bg-rose-500/10 text-rose-700 dark:border-rose-500/40 dark:text-rose-300"
                                }
                              >
                                {s.userFeedback === "helpful" ? "Rated helpful" : "Rated not helpful"}
                              </Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">No user rating</span>
                            )}
                          </div>
                          <div className="flex shrink-0 flex-col items-end leading-none">
                            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                              Overall
                            </span>
                            <span className={cn("mt-1 text-lg font-semibold tabular-nums", text)}>
                              {formatScore(s.compositeScore)}
                              <span className="text-xs font-normal text-muted-foreground"> / 1.00</span>
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <MetricPill
                            label="Grounding"
                            value={formatScore(s.ragQualityScore)}
                            tone={s.ragQualityScore != null ? scoreColor(s.ragQualityScore).text : undefined}
                          />
                          {s.chunkOutcomeSummary?.avgReliability != null ? (
                            <MetricPill
                              label="Sources"
                              value={formatScore(s.chunkOutcomeSummary.avgReliability)}
                              tone={scoreColor(s.chunkOutcomeSummary.avgReliability).text}
                            />
                          ) : null}
                          {s.chunkOutcomeSummary?.chunksUsed != null ? (
                            <MetricPill label="Passages used" value={String(s.chunkOutcomeSummary.chunksUsed)} />
                          ) : null}
                          {s.retrievalLatencyMs != null ? (
                            <MetricPill label="Search time" value={`${Math.round(s.retrievalLatencyMs)} ms`} />
                          ) : null}
                        </div>
                        {s.feedbackReason ? (
                          <p className="mt-2 rounded-md bg-secondary/40 px-2.5 py-1.5 text-xs text-muted-foreground text-pretty">
                            <span className="font-medium text-foreground">Feedback: </span>
                            {s.feedbackReason}
                          </p>
                        ) : null}
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" aria-hidden />
                            {formatTime(s.evaluatedAt)}
                          </span>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <NotYetPopulated>No scored answers match this filter.</NotYetPopulated>
              )}
              {pageCount > 1 ? (
                <div className="mt-4 flex items-center justify-between gap-2">
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
          ) : (
            <NotYetPopulated>
              No scored answers yet. They appear here as people use chat and rate responses.
            </NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
