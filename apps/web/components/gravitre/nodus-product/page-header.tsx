import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

/**
 * Nodus Product Image page header — brand-soft icon tile, divide hairline, compact title.
 */
export function GravitrePageHeader({
  title,
  description,
  icon,
  actions,
  children,
  className,
  eyebrow,
}: {
  title: string
  description?: string
  icon?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  eyebrow?: string
}) {
  return (
    <div
      className={cn(
        "min-w-0 border-b border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-3.5",
        className,
      )}
    >
      <div className="mb-2 flex min-w-0 flex-col justify-between gap-3 sm:mb-2.5 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-3">
          {icon ? (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)] sm:h-10 sm:w-10">
              {icon}
            </div>
          ) : null}
          <div className="min-w-0 space-y-0.5">
            {eyebrow ? <p className={TYPE.eyebrow}>{eyebrow}</p> : null}
            <h1 className={TYPE.pageTitle}>{title}</h1>
            {description ? (
              <p className={cn(TYPE.pageLead, "max-w-2xl")}>{description}</p>
            ) : null}
          </div>
        </div>
        {actions ? (
          <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            {actions}
          </div>
        ) : null}
      </div>
      {children}
    </div>
  )
}
