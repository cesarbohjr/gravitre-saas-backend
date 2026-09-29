"use client"

import type { HTMLAttributes, ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Flat evidence surface: what the thing is, where it came from, and the facts
 * that back it. Used for connector records, documents, observations, artifacts.
 */
export function GravitreContextCard({
  kind,
  mark,
  title,
  subtitle,
  status,
  children,
  footer,
  className,
  ...rest
}: {
  /** Evidence class shown as the eyebrow, e.g. "Connector record", "Observation". */
  kind: string
  mark?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  status?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  className?: string
} & Omit<HTMLAttributes<HTMLElement>, "title">) {
  return (
    <section
      data-context-card=""
      className={cn(
        "rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] dark:border-[color:var(--graphite-700)]",
        className,
      )}
      {...rest}
    >
      <header className="flex items-start gap-2.5 px-3 pb-2 pt-2.5">
        {mark ? <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">{mark}</span> : null}
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-medium text-muted-foreground">{kind}</span>
          <span className="block truncate text-[13.5px] font-semibold text-foreground">{title}</span>
          {subtitle ? <span className="block truncate text-[12px] text-muted-foreground">{subtitle}</span> : null}
        </span>
        {status ? <span className="shrink-0">{status}</span> : null}
      </header>
      {children ? <div className="border-t border-[color:var(--g-border-subtle)] px-3 py-2">{children}</div> : null}
      {footer ? (
        <footer className="border-t border-[color:var(--g-border-subtle)] px-3 py-2 text-[12px] text-muted-foreground">{footer}</footer>
      ) : null}
    </section>
  )
}

/** Label / value fact list inside a context card. `value` of null renders an em dash. */
export function ContextFacts({ facts }: { facts: Array<{ label: string; value: ReactNode | null | undefined }> }) {
  return (
    <dl className="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-x-3 gap-y-1.5 text-[12px]">
      {facts.map((fact) => (
        <div key={fact.label} className="contents">
          <dt className="truncate text-muted-foreground">{fact.label}</dt>
          <dd className="min-w-0 truncate text-right font-medium text-foreground">{fact.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Single readiness check: dot + label, true/false/unknown. */
export function ReadinessCheck({ label, ok }: { label: string; ok: boolean | null | undefined }) {
  const state = ok == null ? "unknown" : ok ? "ok" : "fail"
  return (
    <span data-check={state} className="inline-flex items-center gap-1.5 text-[12px]">
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          state === "ok" && "bg-[color:var(--g-brand)]",
          state === "fail" && "bg-warning",
          state === "unknown" && "bg-muted-foreground/50",
        )}
      />
      <span className={cn(state === "ok" ? "text-foreground" : "text-muted-foreground")}>{label}</span>
      <span className="sr-only">{state === "ok" ? "passing" : state === "fail" ? "failing" : "not reported"}</span>
    </span>
  )
}
