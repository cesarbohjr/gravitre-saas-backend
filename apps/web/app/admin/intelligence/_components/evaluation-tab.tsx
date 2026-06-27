"use client"

import { useMemo } from "react"
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
            <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-background/60 px-6 py-5 text-center">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Composite</span>
              <span
                className={cn(
                  "mt-1 text-4xl font-semibold tabular-nums",
                  compositeColor?.text ?? "text-muted-foreground",
                )}
              >
                {formatScore(composite)}
              </span>
              <span className="mt-0.5 text-xs text-muted-foreground">out of 1.00</span>
              {data ? (
                <span className="mt-2 text-xs text-muted-foreground tabular-nums">
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

        {data ? <LearningToRankCard status={data.retrievalRanker} /> : null}

        <SectionCard
          title="Scored responses"
          description="Recent answers with their individual quality scores."
          icon={<ListChecks className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {samples.length > 0 ? (
            <ul className="divide-y divide-border">
              {samples.map((s) => {
                const { text } = scoreColor(s.compositeScore ?? 0)
                return (
                  <li key={s.id} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <Badge variant="outline">{s.surface}</Badge>
                        {s.userFeedback ? (
                          <Badge
                            variant="secondary"
                            className={
                              s.userFeedback === "helpful"
                                ? "border-emerald-300 text-emerald-700"
                                : "border-rose-300 text-rose-700"
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
