"use client"

import { type ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Info } from "@phosphor-icons/react"

/** Color a 0..1 score: strong (emerald), moderate (amber), weak (rose). */
export function scoreColor(score: number): { bar: string; text: string; glow: string } {
  if (score >= 0.75)
    return {
      bar: "bg-gradient-to-r from-emerald-500 to-teal-400",
      text: "text-emerald-600",
      glow: "shadow-[0_0_12px_-2px] shadow-emerald-500/50",
    }
  if (score >= 0.5)
    return {
      bar: "bg-gradient-to-r from-amber-500 to-yellow-400",
      text: "text-amber-600",
      glow: "shadow-[0_0_12px_-2px] shadow-amber-500/50",
    }
  return {
    bar: "bg-gradient-to-r from-rose-500 to-red-400",
    text: "text-rose-600",
    glow: "shadow-[0_0_12px_-2px] shadow-rose-500/50",
  }
}

export function formatScore(score: number | null): string {
  if (score == null || Number.isNaN(score)) return "—"
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
  if (!value || typeof value !== "string") return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "—"
  return parsed.toLocaleString()
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
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
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
      {/* Brand accent line that reveals on hover */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {icon ? (
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 ring-1 ring-inset ring-emerald-500/20 transition-transform duration-300 group-hover:scale-105 dark:text-emerald-400">
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
