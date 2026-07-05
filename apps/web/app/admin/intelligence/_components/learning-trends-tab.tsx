"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import { learningLevelLabel } from "@/lib/intelligence/visibility-helpers"
import { BanditStatusCard } from "./bandit-status-card"
import { MemoryConflictsCard } from "./memory-conflicts-card"
import { NotYetPopulated, readString as readAdminString, SectionCard } from "./shared"
import { ChartLineUp, Sparkle } from "@phosphor-icons/react"

type SegmentRow = {
  segment_key?: string
  sample_count?: number
  learning_confidence?: string
  outcome_multiplier?: number
}

export function LearningTrendsTab({ enabled }: { enabled: boolean }) {
  const { data: learningHealth, isLoading: learningLoading } = useSWR(
    enabled ? "admin/intelligence/visibility/learning-health" : null,
    () => intelligenceApi.visibilityLearningHealth(),
    { revalidateOnFocus: false },
  )
  const { data: liveDashboard, isLoading: liveLoading } = useSWR(
    enabled ? "admin/intelligence/learning/live-dashboard" : null,
    () => intelligenceApi.learningLiveDashboard(),
    { revalidateOnFocus: false },
  )

  if (!enabled) return null

  const adaptive = (learningHealth?.adaptive_learning as Record<string, unknown> | undefined) ?? {}
  const meta = (learningHealth?.meta_learning as Record<string, unknown> | undefined) ?? {}
  const segments = (adaptive.segment_summaries as SegmentRow[] | undefined) ?? []
  const warnings = [
    ...((adaptive.insufficient_data_warnings as string[] | undefined) ?? []),
    ...((meta.insufficient_data_warnings as string[] | undefined) ?? []),
  ]
  const optimization = (liveDashboard?.domain_optimization as Record<string, unknown> | undefined) ?? {}
  const freshness = (liveDashboard?.knowledge_freshness as Record<string, unknown> | undefined) ?? {}

  return (
    <div className="space-y-6">
      <SectionCard
        title="Adaptive learning trends"
        description="Segment-level learning confidence and outcome multipliers — measured, not fabricated."
        icon={<ChartLineUp className="h-5 w-5" weight="duotone" aria-hidden />}
      >
        {learningLoading ? (
          <p className="text-sm text-muted-foreground">Loading adaptive learning trends…</p>
        ) : segments.length ? (
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-left text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Segment</th>
                  <th className="px-3 py-2 font-medium">Samples</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                  <th className="px-3 py-2 font-medium">Outcome multiplier</th>
                </tr>
              </thead>
              <tbody>
                {segments.slice(0, 12).map((row) => (
                  <tr key={row.segment_key} className="border-b border-border/40 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{readString(row.segment_key, "—")}</td>
                    <td className="px-3 py-2 tabular-nums">{readNumber(row.sample_count, 0)}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="font-normal capitalize">
                        {learningLevelLabel(row.learning_confidence)}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {row.outcome_multiplier != null ? row.outcome_multiplier.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <NotYetPopulated>No adaptive learning segments yet. Outcome events will populate segment learning state.</NotYetPopulated>
        )}
        {warnings.length ? (
          <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
            {warnings.slice(0, 6).map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </SectionCard>

      <SectionCard
        title="Meta-learning guidance"
        description="Soft priors across models, agents, and tools — advisory only."
        icon={<Sparkle className="h-5 w-5" weight="duotone" aria-hidden />}
        delay={0.05}
      >
        {learningLoading ? (
          <p className="text-sm text-muted-foreground">Loading meta-learning summary…</p>
        ) : (
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Guidance segments</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                {readNumber((meta.segment_summaries as unknown[] | undefined)?.length, 0)}
              </dd>
            </div>
            <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Avg guidance strength</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                {(meta.avg_guidance_strength as number | null | undefined) != null
                  ? formatPercent(meta.avg_guidance_strength as number)
                  : "—"}
              </dd>
            </div>
            <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Status</dt>
              <dd className="mt-1 text-sm font-medium capitalize text-foreground">
                {readAdminString(meta.status, "insufficient_data")}
              </dd>
            </div>
          </dl>
        )}
      </SectionCard>

      <BanditStatusCard enabled={enabled} />
      <MemoryConflictsCard enabled={enabled} />

      <SectionCard
        title="Freshness & optimization signals"
        description="Org-wide freshness and pending optimization recommendations consumed by visibility."
        delay={0.1}
      >
        {liveLoading ? (
          <p className="text-sm text-muted-foreground">Loading live learning dashboard…</p>
        ) : (
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-border/60 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Freshness label</dt>
              <dd className="mt-1 text-sm font-medium capitalize text-foreground">
                {readAdminString(freshness.freshness_label, "—")}
              </dd>
            </div>
            <div className="rounded-lg border border-border/60 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Stale sources</dt>
              <dd className="mt-1 text-sm font-medium tabular-nums text-foreground">
                {readNumber((freshness.stale_sources as unknown[] | undefined)?.length, 0)}
              </dd>
            </div>
            <div className="rounded-lg border border-border/60 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Pending optimization</dt>
              <dd className="mt-1 text-sm font-medium tabular-nums text-foreground">
                {readNumber(optimization.pending_count, 0)}
              </dd>
            </div>
            <div className="rounded-lg border border-border/60 px-3 py-2">
              <dt className="text-xs text-muted-foreground">Ready models</dt>
              <dd className="mt-1 text-sm font-medium tabular-nums text-foreground">
                {readNumber(liveDashboard?.ready_model_count, 0)}
              </dd>
            </div>
          </dl>
        )}
        <Badge variant="outline" className="mt-4 border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200">
          advisory_only — recommendations never auto-execute
        </Badge>
      </SectionCard>
    </div>
  )
}
