"use client"

import { cn } from "@/lib/utils"

type AdaptiveDataViewProps = {
  children: React.ReactNode
  className?: string
  /** Minimum width before horizontal scroll kicks in on small screens */
  minWidthClassName?: string
  /**
   * Card/list alternative for narrow viewports. When set, the table/grid
   * children render only from `md` up — no shrunk-table island on phones.
   */
  mobileFallback?: React.ReactNode
}

/**
 * Responsive wrapper for data tables and wide grids.
 * Prefer `mobileFallback` (cards/lists) over horizontal scroll alone.
 */
export function AdaptiveDataView({
  children,
  className,
  minWidthClassName = "min-w-[640px]",
  mobileFallback,
}: AdaptiveDataViewProps) {
  if (mobileFallback) {
    return (
      <>
        <div className={cn("md:hidden", className)}>{mobileFallback}</div>
        <div
          className={cn(
            "hidden w-full overflow-x-auto rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] md:block",
            className,
          )}
        >
          <div className={cn(minWidthClassName, "w-full")}>{children}</div>
        </div>
      </>
    )
  }

  return (
    <div
      className={cn(
        "w-full overflow-x-auto rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]",
        className,
      )}
    >
      <div className={cn(minWidthClassName, "w-full")}>{children}</div>
    </div>
  )
}
