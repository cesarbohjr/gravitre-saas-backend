"use client"

/**
 * Shared filter bar pattern for Activity / Agents / Intelligence hubs.
 * DnD layout is a Phase 3 fast-follow — not included here.
 */

import type { ReactNode } from "react"
import { Filter } from "lucide-react"
import { cn } from "@/lib/utils"

export interface HubFilterBarProps {
  children: ReactNode
  className?: string
  label?: string
  actions?: ReactNode
  /**
   * Chromeless single-row variant for viewport-locked pages, where a bordered
   * card of stacked label-over-control fields costs vertical space the panes
   * need. Controls inline their labels — see `HubFilterField`.
   */
  compact?: boolean
}

export function HubFilterBar({
  children,
  className,
  label = "Filters",
  actions,
  compact = false,
}: HubFilterBarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap gap-3",
        compact
          ? "items-center gap-2"
          : "items-end rounded-lg border border-border bg-card p-3",
        className,
      )}
      data-compact={compact ? "" : undefined}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Filter className="h-3.5 w-3.5" aria-hidden />
        {compact ? <span className="sr-only">{label}</span> : label}
      </div>
      {children}
      {actions ? <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export interface HubFilterFieldProps {
  label: string
  children: ReactNode
  className?: string
  /** Renders the label inline before the control instead of stacked above it. */
  compact?: boolean
}

export function HubFilterField({ label, children, className, compact = false }: HubFilterFieldProps) {
  if (compact) {
    return (
      <div className={cn("flex min-w-0 items-center gap-1.5", className)}>
        <span className="shrink-0 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {children}
      </div>
    )
  }

  return (
    <div className={cn("min-w-[140px]", className)}>
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  )
}
