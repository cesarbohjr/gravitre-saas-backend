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
}

export function HubFilterBar({
  children,
  className,
  label = "Filters",
  actions,
}: HubFilterBarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3",
        className,
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Filter className="h-3.5 w-3.5" aria-hidden />
        {label}
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
}

export function HubFilterField({ label, children, className }: HubFilterFieldProps) {
  return (
    <div className={cn("min-w-[140px]", className)}>
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  )
}
