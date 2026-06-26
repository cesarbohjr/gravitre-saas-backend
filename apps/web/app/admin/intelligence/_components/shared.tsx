"use client"

import { type ReactNode } from "react"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Info } from "@phosphor-icons/react"

/** Color a 0..1 score: strong (emerald), moderate (amber), weak (rose). */
export function scoreColor(score: number): { bar: string; text: string } {
  if (score >= 0.75) return { bar: "bg-emerald-500", text: "text-emerald-600" }
  if (score >= 0.5) return { bar: "bg-amber-500", text: "text-amber-600" }
  return { bar: "bg-rose-500", text: "text-rose-600" }
}

export function formatScore(score: number | null): string {
  if (score == null || Number.isNaN(score)) return "—"
  return score.toFixed(2)
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** A labeled, weighted score bar (e.g. RAG quality 0.8, weight 40%). */
export function ScoreBar({
  label,
  score,
  weight,
}: {
  label: string
  score: number
  weight?: number
}) {
  const clamped = Math.max(0, Math.min(1, score))
  const { bar, text } = scoreColor(clamped)
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-foreground">{label}</span>
        <span className="flex items-baseline gap-2 text-sm">
          <span className={cn("font-semibold tabular-nums", text)}>{formatScore(clamped)}</span>
          {weight != null ? (
            <span className="text-xs text-muted-foreground">weight {formatPercent(weight)}</span>
          ) : null}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuenow={Math.round(clamped * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} score`}
      >
        <div className={cn("h-full rounded-full transition-all", bar)} style={{ width: `${clamped * 100}%` }} />
      </div>
    </div>
  )
}

export function SectionCard({
  title,
  description,
  icon,
  action,
  children,
  className,
}: {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {icon ? <span className="mt-0.5 shrink-0 text-primary">{icon}</span> : null}
          <div>
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            {description ? (
              <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground text-pretty">{description}</p>
            ) : null}
          </div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

/**
 * Honest notice shown when a subsystem has no data yet. Explains the feature
 * populates as the engine runs, without implying anything is live that isn't.
 */
export function NotYetPopulated({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-dashed border-border bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" weight="duotone" aria-hidden />
      <p className="leading-relaxed text-pretty">{children}</p>
    </div>
  )
}

/** Loading / error gate shared across tabs. */
export function TabStateGate({
  isLoading,
  error,
  onRetry,
  children,
}: {
  isLoading: boolean
  error: unknown
  onRetry: () => void
  children: ReactNode
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16" role="status" aria-live="polite">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="sr-only">Loading</span>
      </div>
    )
  }
  if (error) {
    return (
      <ErrorState
        title="Couldn't load intelligence data"
        description="There was a problem loading this section. Please try again."
        onRetry={onRetry}
      />
    )
  }
  return <>{children}</>
}
