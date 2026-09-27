"use client"

import Link from "next/link"
import type { ReactNode } from "react"
import { ArrowRight, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * 3.0 Plus operating language (accepted 2026-09-27), shared by operating routes.
 * Same principles as the Dashboard lanes — live phases, exceptions, intervention,
 * contextual action — without copying the Dashboard layout.
 */

export type PhaseTone = "neutral" | "live" | "attention" | "risk" | "done"

export type OperatingPhase = {
  id: string
  label: string
  /** null = not reported by the backend; never shown as zero. */
  count: number | null
  tone?: PhaseTone
  hint?: string
}

const PHASE_RULE: Record<PhaseTone, string> = {
  neutral: "bg-[color:var(--g-border-strong)]",
  live: "bg-[color:var(--g-brand)]",
  attention: "bg-warning",
  risk: "bg-destructive",
  done: "bg-foreground/70",
}

const PHASE_WASH: Partial<Record<PhaseTone, string>> = {
  attention: "bg-warning/[0.05]",
  risk: "bg-destructive/[0.04]",
}

const FOCUS = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"

/**
 * Full-bleed band of lifecycle phases with live counts. Populated phases carry a
 * coloured top rule; attention/risk phases get a light wash. When `onSelect` is
 * given each phase filters the work below it.
 */
export function PhaseBand({
  phases,
  active,
  onSelect,
  loading,
  label,
  className,
}: {
  phases: OperatingPhase[]
  active?: string | null
  onSelect?: (id: string | null) => void
  loading?: boolean
  label: string
  className?: string
}) {
  return (
    <div
      role={onSelect ? "group" : undefined}
      aria-label={label}
      data-phase-band=""
      className={cn(
        "flex overflow-x-auto border-y border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      {phases.map((phase, index) => {
        const tone = phase.tone ?? "neutral"
        const populated = !loading && (phase.count ?? 0) > 0
        const selected = active === phase.id
        const body = (
          <>
            <span aria-hidden className={cn("absolute inset-x-0 top-0 h-[2px]", populated ? PHASE_RULE[tone] : "bg-transparent")} />
            {selected ? <span aria-hidden className="absolute inset-x-0 bottom-0 h-[2px] bg-foreground" /> : null}
            <span className="flex items-baseline gap-2">
              <span
                className={cn(
                  "text-[22px] font-semibold leading-none tabular-nums tracking-[-0.02em]",
                  populated ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {loading ? "—" : phase.count == null ? "—" : phase.count}
              </span>
              <span className="text-[12.5px] font-medium text-foreground">{phase.label}</span>
            </span>
            {phase.hint ? <span className="mt-1 block truncate text-[11.5px] text-muted-foreground">{phase.hint}</span> : null}
          </>
        )
        const cellClass = cn(
          "relative min-w-[148px] flex-1 px-4 py-3 text-left",
          index > 0 && "border-l border-[color:var(--g-border-subtle)]",
          populated && PHASE_WASH[tone],
        )
        return onSelect ? (
          <button
            key={phase.id}
            type="button"
            aria-pressed={selected}
            data-phase={phase.id}
            onClick={() => onSelect(selected ? null : phase.id)}
            className={cn(cellClass, "transition-colors hover:bg-[color:var(--g-surface-1)]", FOCUS)}
          >
            {body}
          </button>
        ) : (
          <div key={phase.id} data-phase={phase.id} className={cellClass}>
            {body}
          </div>
        )
      })}
    </div>
  )
}

export type InterventionTone = "attention" | "risk" | "live" | "neutral"

const INTERVENE_BAR: Record<InterventionTone, string> = {
  attention: "before:bg-warning",
  risk: "before:bg-destructive",
  live: "before:bg-[color:var(--g-brand)]",
  neutral: "before:bg-muted-foreground/40",
}

/** An item that asks the operator to act: accent bar, semibold title, explicit verb. */
export function InterventionRow({
  title,
  detail,
  meta,
  action,
  href,
  onClick,
  tone = "attention",
  children,
}: {
  title: ReactNode
  detail?: ReactNode
  meta?: ReactNode
  action?: string
  href?: string
  onClick?: () => void
  tone?: InterventionTone
  children?: ReactNode
}) {
  const className = cn(
    "group relative flex w-full items-start gap-3 rounded-[4px] bg-background py-2.5 pl-4 pr-3 text-left shadow-[0_0_0_1px_var(--g-border-subtle)] transition-shadow before:absolute before:inset-y-1.5 before:left-1 before:w-[3px] before:rounded-full hover:shadow-[0_0_0_1px_var(--g-border-strong)]",
    INTERVENE_BAR[tone],
    FOCUS,
  )
  const content = (
    <>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 text-[13px] font-semibold leading-snug text-foreground">{title}</span>
        {detail || meta ? (
          <span className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
            {detail ? <span className="min-w-0 truncate">{detail}</span> : null}
            {detail && meta ? <span aria-hidden>·</span> : null}
            {meta ? <span className="shrink-0 tabular-nums">{meta}</span> : null}
          </span>
        ) : null}
        {children}
      </span>
      {action ? (
        <span className="mt-px inline-flex shrink-0 items-center gap-0.5 rounded-[4px] px-1.5 py-0.5 text-[11.5px] font-medium text-foreground group-hover:bg-[color:var(--g-surface-1)]">
          {action}
          <ArrowRight className="size-3" aria-hidden />
        </span>
      ) : null}
    </>
  )
  if (href) {
    return (
      <Link href={href} data-intervene={tone} className={className}>
        {content}
      </Link>
    )
  }
  return (
    <button type="button" data-intervene={tone} onClick={onClick} className={className}>
      {content}
    </button>
  )
}

/** Full-bleed working section: ruled heading line, content on the canvas (no card). */
export function OperatingSection({
  title,
  count,
  actions,
  children,
  className,
  id,
}: {
  title: string
  count?: number | null
  actions?: ReactNode
  children: ReactNode
  className?: string
  id?: string
}) {
  const headingId = id ?? `section-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`
  return (
    <section aria-labelledby={headingId} className={cn("border-t border-[color:var(--g-border-default)]", className)}>
      <header className="flex items-center justify-between gap-3 px-[var(--np-page-pad-sm)] py-2.5 sm:px-[var(--np-page-pad)]">
        <h2 id={headingId} className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
          {title}
          {count != null ? (
            <span className="rounded-full bg-[color:var(--g-surface-2)] px-1.5 text-[11.5px] font-semibold tabular-nums leading-5 text-foreground">
              {count}
            </span>
          ) : null}
        </h2>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </header>
      {children}
    </section>
  )
}

/**
 * Empty operating surface: say what is empty and show the lifecycle the work will
 * move through, instead of a centred icon. Never invents items.
 */
export function OperatingEmpty({
  title,
  body,
  path,
  action,
  className,
}: {
  title: string
  body?: ReactNode
  /** Lifecycle stages the work moves through, e.g. ["Requested", "Decided", "Executed"]. */
  path?: string[]
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      data-operating-empty=""
      className={cn("px-[var(--np-page-pad-sm)] py-8 sm:px-[var(--np-page-pad)]", className)}
    >
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      {body ? <p className="mt-1 max-w-xl text-[13px] text-muted-foreground">{body}</p> : null}
      {path?.length ? (
        <ol aria-label="How work moves here" className="mt-4 flex flex-wrap items-center gap-1.5 text-[12px]">
          {path.map((stage, index) => (
            <li key={stage} className="flex items-center gap-1.5">
              <span className="rounded-[4px] border border-dashed border-[color:var(--g-border-strong)] px-2 py-1 text-foreground/80">
                {stage}
              </span>
              {index < path.length - 1 ? <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden /> : null}
            </li>
          ))}
        </ol>
      ) : null}
      {action ? <div className="mt-5 flex flex-wrap gap-2">{action}</div> : null}
    </div>
  )
}
