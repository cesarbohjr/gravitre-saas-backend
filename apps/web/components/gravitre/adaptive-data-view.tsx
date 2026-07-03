"use client"

import { cn } from "@/lib/utils"

type AdaptiveDataViewProps = {
  children: React.ReactNode
  className?: string
  /** Minimum width before horizontal scroll kicks in on small screens */
  minWidthClassName?: string
}

/**
 * Responsive wrapper for data tables and wide grids — scrolls horizontally on
 * narrow viewports instead of breaking layout.
 */
export function AdaptiveDataView({
  children,
  className,
  minWidthClassName = "min-w-[640px]",
}: AdaptiveDataViewProps) {
  return (
    <div className={cn("w-full overflow-x-auto rounded-lg border border-border", className)}>
      <div className={cn(minWidthClassName, "w-full")}>{children}</div>
    </div>
  )
}
