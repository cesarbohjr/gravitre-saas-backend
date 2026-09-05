"use client"

/**
 * EditTool-inspired write-authority chrome (ADAPT).
 * Same PreActionCard payload + handlers — retokened header only; no layout/IA change.
 */

import Link from "next/link"
import { CheckCircle2, Loader2, Pencil, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { NucleoApproval } from "@/components/icons/nucleo/semantic"
import type { PreActionCardPayload, PreActionRiskLevel } from "@/lib/pre-action-card"

type PreActionCardProps = {
  payload: PreActionCardPayload
  /** Dense strip for chat; fuller layout for Approvals detail. */
  variant?: "chat" | "approvals"
  confirming?: boolean
  approveLabel?: string
  onApprove?: () => void
  onReject?: () => void
  onModify?: () => void
  className?: string
  /** Hide footer actions (e.g. Approvals page owns Approve/Reject). */
  hideActions?: boolean
}

function riskTone(level?: PreActionRiskLevel): string {
  if (level === "high") return STATUS.rejected
  if (level === "medium") return STATUS.pending
  if (level === "low") return STATUS.verified
  return STATUS.idle
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/40 py-1.5 last:border-0">
      <span className={TYPE.meta}>{label}</span>
      <span className="shrink-0 text-right text-xs font-medium capitalize text-foreground">{value}</span>
    </div>
  )
}

export function PreActionCard({
  payload,
  variant = "chat",
  confirming = false,
  approveLabel,
  onApprove,
  onReject,
  onModify,
  className,
  hideActions = false,
}: PreActionCardProps) {
  const showExplain =
    Boolean(payload.estimatedImpact) ||
    Boolean(payload.riskLevel) ||
    Boolean(payload.approvalReason) ||
    Boolean(payload.entity)

  const modifyHref =
    !onModify && payload.source === "approvals_queue" && payload.conversationId
      ? `/ai?conversation=${encodeURIComponent(payload.conversationId)}`
      : null

  const title =
    variant === "chat"
      ? payload.requiresApproval
        ? "Approval required"
        : "Ready to execute"
      : "Pre-action review"

  return (
    <div
      className={cn(
        "overflow-hidden border bg-card text-sm",
        RADIUS.card,
        variant === "chat"
          ? "border-[color:var(--status-pending)]/30"
          : "border-border",
        className,
      )}
      data-testid="pre-action-card"
      data-source={payload.source}
      data-risk={payload.riskLevel || ""}
      data-impact={payload.estimatedImpact || ""}
    >
      <div
        className={cn(
          "flex h-8 items-center gap-1.5 border-b border-border px-3",
          variant === "chat" ? STATUS.pending : "bg-muted/40 text-muted-foreground",
          "rounded-none border-x-0 border-t-0",
        )}
      >
        <NucleoApproval className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className={cn(TYPE.meta, "truncate font-medium")}>{title}</span>
      </div>

      <div className="min-w-0 space-y-1 bg-background px-3 py-2.5">
        <p className="text-sm font-medium text-foreground">{payload.title}</p>
        {payload.description ? (
          <p className="text-xs text-muted-foreground">{payload.description}</p>
        ) : null}

        {showExplain ? (
          <div className="mt-2 space-y-0.5" data-testid="pre-action-explain">
            {payload.entity ? <DetailRow label="Entity" value={payload.entity} /> : null}
            {payload.action && payload.action !== payload.title ? (
              <DetailRow label="Action" value={payload.action} />
            ) : null}
            {payload.estimatedImpact ? (
              <DetailRow label="Impact" value={payload.estimatedImpact} />
            ) : null}
            {payload.riskLevel ? (
              <div className="flex items-center justify-between gap-3 border-b border-border/40 py-1.5 last:border-0">
                <span className={TYPE.meta}>Risk</span>
                <span
                  className={cn(
                    "inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                    riskTone(payload.riskLevel),
                  )}
                >
                  {payload.riskLevel}
                </span>
              </div>
            ) : null}
            {payload.approvalReason ? (
              <DetailRow label="Why approval" value={payload.approvalReason} />
            ) : null}
          </div>
        ) : null}

        {!hideActions && (onApprove || onReject || onModify || modifyHref) ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {onApprove ? (
              <Button size="sm" className="h-8" disabled={confirming} onClick={onApprove}>
                {confirming ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    {approveLabel || "Approving…"}
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                    {approveLabel || "Approve"}
                  </>
                )}
              </Button>
            ) : null}
            {onReject ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                disabled={confirming}
                onClick={onReject}
              >
                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                Reject
              </Button>
            ) : null}
            {onModify ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 text-muted-foreground"
                disabled={confirming}
                onClick={onModify}
              >
                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                Modify
              </Button>
            ) : null}
            {modifyHref ? (
              <Button size="sm" variant="ghost" className="h-8 text-muted-foreground" asChild>
                <Link href={modifyHref}>
                  <Pencil className="mr-1.5 h-3.5 w-3.5" />
                  Modify
                </Link>
              </Button>
            ) : null}
          </div>
        ) : null}

        {payload.modifyHint && (onModify || modifyHref) ? (
          <p className="mt-2 text-[11px] text-muted-foreground">{payload.modifyHint}</p>
        ) : null}
      </div>
    </div>
  )
}
