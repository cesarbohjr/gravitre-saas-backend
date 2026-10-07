"use client"

/** "Audit trail": every promote, reject and rollback decision, newest first. */
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { memoryPromotionApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { plainDecisionReasoning } from "@/lib/intelligence/helpers"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ORG_MEMORY_SWR_KEYS } from "./use-org-memory"

const ACTION_LABELS: Record<string, string> = {
  promote: "Shared org-wide",
  reject: "Rejected",
  rollback: "Rolled back",
  expire: "Expired",
}

const PATH_LABELS: Record<string, string> = {
  auto: "automatically",
  manual_approval: "by a person",
}

function actionLabel(row: Record<string, unknown>): string {
  const action = String(row.action ?? "").toLowerCase()
  const base = ACTION_LABELS[action] ?? (action ? action.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "Decision")
  const path = PATH_LABELS[String(row.promotion_path ?? row.promotionPath ?? "")]
  return action === "promote" && path ? `${base} ${path}` : base
}

export function MemoryAuditSheet({
  open,
  onOpenChange,
  enabled,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  enabled: boolean
}) {
  const { data, error, mutate } = useSWR(enabled && open ? ORG_MEMORY_SWR_KEYS.audit : null, () =>
    memoryPromotionApi.audit({ limit: 50 }),
  )
  const items = (data?.items as Array<Record<string, unknown>> | undefined) ?? []

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-md">
        <SheetHeader className="border-b border-divide">
          <SheetTitle>Audit trail</SheetTitle>
          <SheetDescription>Every memory Gravitre shared, rejected or rolled back, newest first.</SheetDescription>
        </SheetHeader>
        <div className="p-4">
          {error ? (
            <ErrorState
              title="Unable to load the audit trail"
              description={error instanceof ApiError ? error.message : "Please try again."}
              onRetry={() => mutate()}
            />
          ) : !data ? (
            <p className={TYPE.bodyMuted}>Loading audit trail…</p>
          ) : items.length === 0 ? (
            <p className={TYPE.bodyMuted}>No memory decisions yet. They appear here when a memory is approved, rejected or rolled back.</p>
          ) : (
            <ol className="divide-y divide-divide">
              {items.map((row, index) => {
                const decidedAt = typeof row.decided_at === "string" ? row.decided_at : null
                return (
                  <li key={String(row.id ?? index)} className="space-y-1 py-3 first:pt-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-sm font-medium text-[color:var(--g-text-primary)]">{actionLabel(row)}</span>
                      <span className={cn(TYPE.meta, "shrink-0")}>
                        {decidedAt ? formatDistanceToNow(new Date(decidedAt), { addSuffix: true }) : "—"}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
                      {plainDecisionReasoning(row.decisionReasoning ?? row.decision_reasoning)}
                    </p>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
