"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { Gauge, ListChecks, Clock, Hash } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, ScoreBar, scoreColor, formatScore, formatTime } from "./shared"
import { LearningToRankCard } from "./learning-to-rank-card"
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"

/** A compact labeled metric shown on a scored-response row. */
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
    () => intelligenceApi.evaluations({ limit: 50 }),
    { revalidateOnFocus: false },
  )

  const composite = data?.summary.avgCompositeScore ?? null
  const compositeColor = composite != null ? scoreColor(composite) : null

  // Derive the three weighted component scores from the real summary + records.
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
      { key: "rag", label: "RAG quality", score: summary.avgRagQualityScore, weight: compositeScoreWeights.ragQualityScore },
      { key: "feedback", label: "User feedback", score: feedbackScore, weight: compositeScoreWeights.userFeedback },
      { key: "reliability", label: "Source reliability", score: reliabilityScore, weight: compositeScoreWeights.chunkReliabilityAvg },
    ]
  }, [data])

  const samples = data?.evaluations ?? []

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
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
                Composite
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
                  {data.summary.totalEvaluations} evaluation{data.summary.totalEvaluations === 1 ? "" : "s"}
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
                No responses have been scored yet. The composite score and its component breakdown populate as the
                engine answers questions and collects feedback.
              </NotYetPopulated>
            </div>
          ) : null}
        </SectionCard>

        {data ? <LearningToRankCard status={data.retrievalRanker} delay={0.06} /> : null}

        <SectionCard
          title={SURFACE_COPY.learningAdmin.scoredResponsesTitle}
          description="Recent answers with their individual quality scores."
          icon={<ListChecks className="h-5 w-5" weight="duotone" aria-hidden />}
          delay={0.12}
        >
          {samples.length > 0 ? (
            <ul className="divide-y divide-border">
              {samples.map((s) => {
                const { text } = scoreColor(s.compositeScore ?? 0)
                return (
                  <li
                    key={s.id}
                    className="-mx-2 rounded-lg px-2 py-3 transition-colors first:pt-0 last:pb-0 hover:bg-secondary/50"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <Badge variant="outline" className="capitalize">
                          {s.surface}
                        </Badge>
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
                          Overall quality
                        </span>
                        <span className={cn("mt-1 text-lg font-semibold tabular-nums", text)}>
                          {formatScore(s.compositeScore)}
                          <span className="text-xs font-normal text-muted-foreground"> / 1.00</span>
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <MetricPill
                        label="RAG quality"
                        value={formatScore(s.ragQualityScore)}
                        tone={s.ragQualityScore != null ? scoreColor(s.ragQualityScore).text : undefined}
                      />
                      {s.chunkOutcomeSummary?.avgReliability != null ? (
                        <MetricPill
                          label="Source reliability"
                          value={formatScore(s.chunkOutcomeSummary.avgReliability)}
                          tone={scoreColor(s.chunkOutcomeSummary.avgReliability).text}
                        />
                      ) : null}
                      {s.chunkOutcomeSummary?.chunksUsed != null ? (
                        <MetricPill label="Chunks used" value={String(s.chunkOutcomeSummary.chunksUsed)} />
                      ) : null}
                      {s.retrievalLatencyMs != null ? (
                        <MetricPill label="Retrieval" value={`${Math.round(s.retrievalLatencyMs)} ms`} />
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
                      <span className="inline-flex items-center gap-1 font-mono" title={`Message ${s.messageId}`}>
                        <Hash className="h-3 w-3" aria-hidden />
                        {s.messageId.slice(0, 8)}
                      </span>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <NotYetPopulated>
              No scored responses yet. Individual answers and their scores appear here as the engine is used.
            </NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
