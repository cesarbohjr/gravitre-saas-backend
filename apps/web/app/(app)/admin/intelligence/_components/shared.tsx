"use client"

import { type ReactNode } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"
import { ErrorState } from "@/components/gravitre/empty-state"
import { formatDateTimeHuman } from "@/lib/intelligence/helpers"
import { Info } from "@phosphor-icons/react"

/** Color a 0..1 score: strong (emerald), moderate (amber), weak (rose). */
export function scoreColor(score: number): { bar: string; text: string; glow: string } {
  if (score >= 0.75)
    return {
      bar: "bg-[color:var(--g-emerald)]",
      text: "text-emerald-600",
      glow: "",
    }
  if (score >= 0.5)
    return {
      bar: "bg-amber-500",
      text: "text-amber-600",
      glow: "",
    }
  return {
    bar: "bg-rose-500",
    text: "text-rose-600",
    glow: "",
  }
}

export function formatScore(score: number | null): string {
  if (score == null || !Number.isFinite(score)) return "—"
  return score.toFixed(2)
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** Coerce an unknown value to a finite number, with a fallback. */
export function readNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/** Coerce an unknown value to a trimmed string, with a fallback. */
export function readString(value: unknown, fallback = ""): string {
  if (value == null) return fallback
  return String(value)
}

/** Format an ISO timestamp for display, or an em dash when absent/invalid. */
export function formatTime(value: unknown): string {
  return formatDateTimeHuman(value)
}

/** A labeled, weighted score bar (e.g. RAG quality 0.8, weight 40%). */
export function ScoreBar({
  label,
  score,
  weight,
}: {
  label: string
  score: number | null | undefined
  weight?: number
}) {
  const reduced = useReducedMotion()
  if (score == null || !Number.isFinite(score)) return <div className="flex items-baseline justify-between gap-2 text-sm"><span>{label}</span><span className="text-muted-foreground">Not reported</span></div>
  const clamped = Math.max(0, Math.min(1, score))
  const { bar, text, glow } = scoreColor(clamped)
  return (
    <div className="group/score">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-foreground">{label}</span>
        <span className="flex items-baseline gap-2 text-sm">
          <span className={cn("font-semibold tabular-nums transition-colors", text)}>{formatScore(clamped)}</span>
          {weight != null ? (
            <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
              weight {formatPercent(weight)}
            </span>
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
        <motion.div
          className={cn("h-full rounded-full", bar, glow)}
          initial={{ width: 0 }}
          animate={{ width: `${clamped * 100}%` }}
          transition={{ duration: reduced ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
        />
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
  delay = 0,
}: {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  /** Stagger delay (seconds) for the entrance animation. */
  delay?: number
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border/70 bg-card p-5 shadow-sm",
        "transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-500/30 hover:shadow-md hover:shadow-emerald-500/5",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {icon ? (
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-[color:var(--g-emerald-pale)] text-[color:var(--g-emerald-deep)] ring-1 ring-inset ring-[color:var(--g-emerald)]/20">
              {icon}
            </span>
          ) : null}
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
    </motion.section>
  )
}

/**
 * Honest notice shown when a subsystem has no data yet. Explains the feature
 * populates as the engine runs, without implying anything is live that isn't.
 */
export function NotYetPopulated({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-[8px] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-3 text-sm text-muted-foreground">
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
  hasData = false,
  children,
}: {
  isLoading: boolean
  error: unknown
  onRetry: () => void
  hasData?: boolean
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
  if (error && !hasData) {
    return (
      <ErrorState
        title="Couldn't load intelligence data"
        description="There was a problem loading this section. Please try again."
        onRetry={onRetry}
      />
    )
  }
  return <>{error ? <ErrorState title="Intelligence data could not refresh" description="Showing the last loaded snapshot." onRetry={onRetry} /> : null}{children}</>
}
