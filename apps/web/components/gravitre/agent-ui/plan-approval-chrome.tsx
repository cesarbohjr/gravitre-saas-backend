"use client"

/**
 * Agent Elements–inspired plan approval chrome (ADAPT).
 * Visual wrapper only — approve/reject handlers stay on existing Gravitre flows.
 */

import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { NucleoApproval } from "@/components/icons/nucleo/semantic"

export function PlanApprovalChrome({
  title,
  summary,
  children,
  className,
}: {
  title: string
  summary?: string | null
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "overflow-hidden border bg-card",
        RADIUS.panel,
        "border-[color:var(--status-pending)]/30",
        className,
      )}
    >
      <div
        className={cn(
          "flex h-8 items-center justify-between gap-2 border-b border-border px-3",
          STATUS.pending,
          "rounded-none border-x-0 border-t-0",
        )}
      >
        <div className="flex min-w-0 items-center gap-1.5">
          <NucleoApproval className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className={cn(TYPE.meta, "truncate font-medium")}>{title}</span>
        </div>
      </div>
      <div className="space-y-2 bg-background px-3 py-2.5">
        {summary ? <p className="text-sm text-foreground">{summary}</p> : null}
        {children}
      </div>
    </div>
  )
}
