"use client"

import type { IntelligenceEvaluationsResponse } from "@/lib/api"
import { cn } from "@/lib/utils"
import { ShieldCheck, Lightning, Clock } from "@phosphor-icons/react"
import { SectionCard } from "./shared"

type RetrievalRankerStatus = IntelligenceEvaluationsResponse["retrievalRanker"]

function formatDate(value: string | null): string {
  if (!value) return "never"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return "never"
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

/**
 * Where the active/learned weight (or the default) sits within its hard safety
 * bounds. Makes it visually obvious the weight can never exceed the safe range.
 */
function WeightOnBoundsTrack({
  value,
  min,
  max,
  active,
}: {
  value: number
  min: number
  max: number
  active: boolean
}) {
  const span = Math.max(max - min, 0.0001)
  const pct = Math.max(0, Math.min(1, (value - min) / span)) * 100
  return (
    <div className="mt-2">
      <div className="relative h-2 w-full rounded-full bg-secondary">
        <div className="absolute inset-y-0 left-0 rounded-full bg-primary/20" style={{ width: `${pct}%` }} />
        <div
          className={cn(
            "absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background shadow",
            active ? "bg-emerald-500" : "bg-muted-foreground",
          )}
          style={{ left: `${pct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] tabular-nums text-muted-foreground">
        <span>min {min.toFixed(2)}</span>
        <span>max {max.toFixed(2)}</span>
      </div>
    </div>
  )
}

export function LearningToRankCard({ status }: { status: RetrievalRankerStatus }) {
  const active = status.usingLearnedWeight
  const trainingExamples = status.trainingExamples
  const trainingThreshold = status.minTrainingExamples
  const defaultWeight = status.fallbackReliabilityWeight
  const learnedWeight = active ? status.activeReliabilityWeight : null
  const weightBounds = { min: status.minLearnedWeight, max: status.maxLearnedWeight }
  const lastTrainedAt = status.lastTrainedAt
  const progressPct = Math.max(0, Math.min(1, trainingExamples / Math.max(trainingThreshold, 1))) * 100

  return (
    <SectionCard
      title="Learning-to-rank status"
      description="Whether the self-improving ranker is active for this org, and the safe bounds its weight is held within."
      icon={<ShieldCheck className="h-5 w-5" weight="duotone" aria-hidden />}
      action={
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            active ? "bg-emerald-500/10 text-emerald-700" : "bg-secondary text-muted-foreground",
          )}
        >
          <Lightning className="h-3.5 w-3.5" weight="duotone" aria-hidden />
          {active ? "Active" : "Default weight"}
        </span>
      }
    >
      {active && learnedWeight != null ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
            <p className="text-sm text-emerald-900">
              Learned weight:{" "}
              <span className="font-semibold tabular-nums">{learnedWeight.toFixed(2)}</span>{" "}
              <span className="text-emerald-700">
                (bounded range: {weightBounds.min.toFixed(2)}–{weightBounds.max.toFixed(2)})
              </span>
            </p>
            <WeightOnBoundsTrack value={learnedWeight} min={weightBounds.min} max={weightBounds.max} active />
            <p className="mt-2 text-xs leading-relaxed text-emerald-800 text-pretty">
              This weight is learned from real feedback but clamped to the range above, so it can never
              destabilize ranking the way an unbounded value could.
            </p>
          </div>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-background/60 p-3">
              <dt className="text-xs text-muted-foreground">Training examples</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
                {trainingExamples.toLocaleString()}
              </dd>
            </div>
            <div className="rounded-xl border border-border bg-background/60 p-3">
              <dt className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" weight="duotone" aria-hidden />
                Last trained
              </dt>
              <dd className="mt-0.5 font-semibold text-foreground">{formatDate(lastTrainedAt)}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-secondary/40 p-4">
            <p className="text-sm text-foreground">
              Using default weight{" "}
              <span className="font-semibold tabular-nums">{defaultWeight.toFixed(2)}</span>{" "}
              <span className="text-muted-foreground">
                (bounded range: {weightBounds.min.toFixed(2)}–{weightBounds.max.toFixed(2)})
              </span>
            </p>
            <WeightOnBoundsTrack value={defaultWeight} min={weightBounds.min} max={weightBounds.max} active={false} />
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
              The ranker hasn&apos;t trained yet, so it falls back to this fixed default. Once active, any
              learned weight stays within the same safe bounds.
            </p>
          </div>
          <div>
            <div className="flex items-baseline justify-between text-sm">
              <span className="text-foreground">Training progress</span>
              <span className="tabular-nums text-muted-foreground">
                {trainingExamples} / {trainingThreshold} examples
              </span>
            </div>
            <div
              className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-secondary"
              role="progressbar"
              aria-valuenow={trainingExamples}
              aria-valuemin={0}
              aria-valuemax={trainingThreshold}
              aria-label="Training examples collected"
            >
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progressPct}%` }} />
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {trainingExamples} / {trainingThreshold} training examples collected — using default weight{" "}
              {defaultWeight.toFixed(2)} until then.
            </p>
          </div>
        </div>
      )}
    </SectionCard>
  )
}
