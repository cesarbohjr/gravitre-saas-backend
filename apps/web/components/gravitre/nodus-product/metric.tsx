import Link from "next/link"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Nodus Product Image KPI card — hairline border, aceternity shadow, compact metric.
 * Real values only; callers pass "—" when data is unavailable.
 */
export function GravitreMetric({
  label,
  value,
  hint,
  href,
  icon,
  warning = false,
  className,
}: {
  label: string
  value: ReactNode
  hint?: string
  href?: string
  icon?: ReactNode
  warning?: boolean
  className?: string
}) {
  const body = (
    <>
      {icon ? (
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)]",
            warning
              ? "bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]"
              : "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
          )}
        >
          {icon}
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium tracking-wide text-[color:var(--g-text-muted)]">
          {label}
        </p>
        <p className="mt-0.5 text-xl font-semibold tabular-nums tracking-tight text-[color:var(--g-text-primary)]">
          {value}
        </p>
        {hint ? (
          <p className="mt-0.5 truncate text-[11px] text-[color:var(--g-text-muted)] group-hover:text-[color:var(--g-text-secondary)]">
            {hint}
          </p>
        ) : null}
      </div>
    </>
  )

  const classes = cn(
    "group flex items-start gap-3 rounded-[var(--np-radius-lg)] border bg-[color:var(--g-surface-1)] p-3 shadow-[var(--np-shadow)] transition-colors",
    warning ? "border-amber-300/70" : "border-divide",
    href && "hover:bg-[color:var(--g-surface-2)]",
    className,
  )

  if (href) {
    return (
      <Link href={href} className={classes}>
        {body}
      </Link>
    )
  }

  return <div className={classes}>{body}</div>
}

export function GravitreSurface({
  children,
  className,
  padded = true,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]",
        padded && "p-5 sm:p-6",
        className,
      )}
    >
      {children}
    </div>
  )
}
