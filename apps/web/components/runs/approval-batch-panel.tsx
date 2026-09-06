"use client"

import { useMemo, useState } from "react"
import { formatStatusLabel } from "@/components/gravitre/status-badge"
import { StatusChip } from "@/components/gravitre/visual"
import { Button } from "@/components/ui/button"
import { CheckCircle, Loader2, XCircle } from "lucide-react"
import type { ApprovalBatchItemView, ApprovalBatchView } from "@/types/api"

type ItemDecision = "approved" | "rejected"

interface ApprovalBatchPanelProps {
  batch: ApprovalBatchView
  disabled?: boolean
  isSubmitting?: boolean
  onSubmit: (decisions: Array<{ itemKey: string; decision: ItemDecision; comment?: string }>) => Promise<void>
}

export function ApprovalBatchPanel({
  batch,
  disabled,
  isSubmitting,
  onSubmit,
}: ApprovalBatchPanelProps) {
  const pendingItems = useMemo(
    () => batch.items.filter((item) => item.status === "pending"),
    [batch.items],
  )
  const [decisions, setDecisions] = useState<Record<string, ItemDecision>>({})

  const setDecision = (itemKey: string, decision: ItemDecision) => {
    setDecisions((current) => ({ ...current, [itemKey]: decision }))
  }

  const handleSubmit = async () => {
    const payload = pendingItems
      .map((item) => {
        const decision = decisions[item.itemKey]
        if (!decision) return null
        return { itemKey: item.itemKey, decision }
      })
      .filter(Boolean) as Array<{ itemKey: string; decision: ItemDecision }>
    if (payload.length !== pendingItems.length) return
    await onSubmit(payload)
    setDecisions({})
  }

  const allDecided = pendingItems.every((item) => decisions[item.itemKey])

  return (
    <div className="mb-4 space-y-3 rounded-md border border-border bg-background/60 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Batch review ({batch.items.length} items)
      </p>
      <ul className="space-y-2">
        {batch.items.map((item) => (
          <BatchItemRow
            key={item.itemKey}
            item={item}
            decision={decisions[item.itemKey]}
            disabled={disabled || isSubmitting || item.status !== "pending"}
            onDecision={setDecision}
          />
        ))}
      </ul>
      {pendingItems.length > 0 && (
        <Button
          size="sm"
          className="h-8"
          disabled={disabled || isSubmitting || !allDecided}
          onClick={() => void handleSubmit()}
        >
          {isSubmitting ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
          Submit batch decisions
        </Button>
      )}
    </div>
  )
}

function BatchItemRow({
  item,
  decision,
  disabled,
  onDecision,
}: {
  item: ApprovalBatchItemView
  decision?: ItemDecision
  disabled?: boolean
  onDecision: (itemKey: string, decision: ItemDecision) => void
}) {
  const statusLabel =
    item.status === "pending" ? (decision ? decision : "pending") : item.status

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2">
      <div>
        <p className="text-sm font-medium text-foreground">{item.label}</p>
        {item.sourceNodeId ? (
          <p className="text-xs text-muted-foreground">from {item.sourceNodeId}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        {item.status !== "pending" ? (
          <StatusChip status={String(statusLabel)}>
            {formatStatusLabel(String(statusLabel))}
          </StatusChip>
        ) : (
          <>
            {decision ? (
              <StatusChip status={decision}>{formatStatusLabel(decision)}</StatusChip>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant={decision === "approved" ? "default" : "outline"}
              className="h-7 gap-1 px-2"
              disabled={disabled}
              onClick={() => onDecision(item.itemKey, "approved")}
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Approve
            </Button>
            <Button
              type="button"
              size="sm"
              variant={decision === "rejected" ? "destructive" : "outline"}
              className="h-7 gap-1 px-2"
              disabled={disabled}
              onClick={() => onDecision(item.itemKey, "rejected")}
            >
              <XCircle className="h-3.5 w-3.5" />
              Reject
            </Button>
          </>
        )}
      </div>
    </li>
  )
}
