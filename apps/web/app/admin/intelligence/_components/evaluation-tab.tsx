"use client"

import { useMemo } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { Gauge, ListChecks } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, ScoreBar, scoreColor, formatScore, formatTime } from "./shared"
import { LearningToRankCard } from "./learning-to-rank-card"
import { cn } from "@/lib/utils"

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
          title="Response quality"
          description="A composite score for how good the engine's answers are, blending three weighted signals."
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
          title="Scored responses"
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
                        <Badge variant="outline">{s.surface}</Badge>
                        {s.userFeedback ? (
                          <Badge
                            variant="secondary"
                            className={
                              s.userFeedback === "helpful"
                                ? "border-emerald-300 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/40 dark:text-emerald-300"
                                : "border-rose-300 bg-rose-500/10 text-rose-700 dark:border-rose-500/40 dark:text-rose-300"
                            }
                          >
                            {s.userFeedback === "helpful" ? "helpful" : "not helpful"}
                          </Badge>
                        ) : null}
                        <span className="truncate text-xs text-muted-foreground">msg {s.messageId.slice(0, 8)}</span>
                      </div>
                      <span className={cn("shrink-0 text-sm font-semibold tabular-nums", text)}>
                        {formatScore(s.compositeScore)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
                      <span>RAG {formatScore(s.ragQualityScore)}</span>
                      <span>
                        Reliability{" "}
                        {s.chunkOutcomeSummary?.avgReliability != null
                          ? formatScore(s.chunkOutcomeSummary.avgReliability)
                          : "—"}
                      </span>
                      {s.retrievalLatencyMs != null ? <span>{Math.round(s.retrievalLatencyMs)}ms retrieval</span> : null}
                      <span>{formatTime(s.evaluatedAt)}</span>
                    </div>
                    {s.feedbackReason ? (
                      <p className="mt-1 text-xs text-muted-foreground text-pretty">{s.feedbackReason}</p>
                    ) : null}
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
