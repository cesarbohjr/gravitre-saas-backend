import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Nodus Product Image table shell — hairline divide, aceternity shadow, compact row height.
 */
export function GravitreTableShell({
  children,
  className,
  toolbar,
}: {
  children: ReactNode
  className?: string
  toolbar?: ReactNode
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]",
        className,
      )}
    >
      {toolbar ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-divide px-4 py-2.5">
          {toolbar}
        </div>
      ) : null}
      <div className="overflow-x-auto">{children}</div>
    </div>
  )
}

export function GravitreTable({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <table
      className={cn(
        "w-full min-w-[420px] text-left text-sm",
        className,
      )}
    >
      {children}
    </table>
  )
}

export function GravitreTh({
  children,
  className,
}: {
  children?: ReactNode
  className?: string
}) {
  return (
    <th
      className={cn(
        "h-[var(--np-row-h,40px)] border-b border-divide px-4 text-xs font-medium text-[color:var(--g-text-muted)]",
        className,
      )}
    >
      {children}
    </th>
  )
}

export function GravitreTd({
  children,
  className,
}: {
  children?: ReactNode
  className?: string
}) {
  return (
    <td
      className={cn(
        "h-[var(--np-row-h,40px)] border-b border-divide/70 px-4 text-[color:var(--g-text-primary)] last:border-0",
        className,
      )}
    >
      {children}
    </td>
  )
}
