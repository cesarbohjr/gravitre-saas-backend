"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import type { EvaluationData } from "@/lib/admin-intelligence"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Gauge, ListChecks } from "@phosphor-icons/react"
import {
  SectionCard,
  NotYetPopulated,
  TabStateGate,
  ScoreBar,
  scoreColor,
  formatScore,
} from "./shared"
import { LearningToRankCard } from "./learning-to-rank-card"
import { cn } from "@/lib/utils"

export function EvaluationTab({ active }: { active: boolean }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR<EvaluationData>(
    active ? "/api/admin/intelligence/evaluation" : null,
    fetcher,
    { revalidateOnFocus: false },
  )

  const composite = data?.compositeScore ?? null
  const compositeColor = composite != null ? scoreColor(composite) : null

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
        <div className="flex justify-end">
          <DataFreshness
            updatedAt={data?.generatedAt ?? undefined}
            isRefreshing={isValidating}
            onRefresh={() => mutate()}
          />
        </div>

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
            </div>

            <div className="space-y-4">
              {data?.components.map((c) => (
                <ScoreBar key={c.key} label={c.label} score={c.score} weight={c.weight} />
              ))}
            </div>
          </div>

          {composite == null ? (
            <div className="mt-4">
              <NotYetPopulated>
                No responses have been scored yet. The composite score and its component breakdown
                populate as the engine answers questions and collects feedback.
              </NotYetPopulated>
            </div>
          ) : null}
        </SectionCard>

        {data ? <LearningToRankCard status={data.learningToRank} /> : null}

        <SectionCard
          title="Scored responses"
          description="Recent answers with their individual quality scores."
          icon={<ListChecks className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.samples.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.samples.map((s) => {
                const { text } = scoreColor(s.compositeScore)
                return (
                  <li key={s.id} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex items-start justify-between gap-4">
                      <p className="min-w-0 text-sm text-foreground text-pretty">{s.query}</p>
                      <span className={cn("shrink-0 text-sm font-semibold tabular-nums", text)}>
                        {formatScore(s.compositeScore)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
                      <span>RAG {formatScore(s.ragQuality)}</span>
                      <span>Feedback {s.userFeedback == null ? "—" : formatScore(s.userFeedback)}</span>
                      <span>Source {formatScore(s.sourceReliability)}</span>
                      <span>{new Date(s.createdAt).toLocaleDateString()}</span>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <NotYetPopulated>
              No scored responses yet. Individual answers and their scores will appear here as the
              engine is used.
            </NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
