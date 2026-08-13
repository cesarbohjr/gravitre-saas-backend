"use client"

import Link from "next/link"
import { CheckCircle2, Loader2, Pencil, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
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
  if (level === "high") return "border-destructive/30 bg-destructive/10 text-destructive"
  if (level === "medium") return "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300"
  if (level === "low") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
  return "border-border bg-muted/40 text-muted-foreground"
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 border-b border-border/40 last:border-0">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-xs font-medium text-foreground text-right capitalize">{value}</span>
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

  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3 text-sm",
        variant === "chat"
          ? "border-amber-500/25 bg-amber-500/5"
          : "border-border bg-card",
        className,
      )}
      data-testid="pre-action-card"
      data-source={payload.source}
      data-risk={payload.riskLevel || ""}
      data-impact={payload.estimatedImpact || ""}
    >
      <div className="min-w-0">
        {variant === "chat" ? (
          <p className="text-xs font-medium uppercase tracking-wide text-amber-700 dark:text-amber-400">
            {payload.requiresApproval ? "Approval required" : "Ready to execute"}
          </p>
        ) : (
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
            Pre-action review
          </p>
        )}
        <p className="mt-1 text-sm font-medium text-foreground">{payload.title}</p>
        {payload.description ? (
          <p className="mt-1 text-xs text-muted-foreground">{payload.description}</p>
        ) : null}

        {showExplain ? (
          <div className="mt-3 space-y-0.5" data-testid="pre-action-explain">
            {payload.entity ? <DetailRow label="Entity" value={payload.entity} /> : null}
            {payload.action && payload.action !== payload.title ? (
              <DetailRow label="Action" value={payload.action} />
            ) : null}
            {payload.estimatedImpact ? (
              <DetailRow label="Impact" value={payload.estimatedImpact} />
            ) : null}
            {payload.riskLevel ? (
              <div className="flex items-center justify-between gap-3 py-1.5 border-b border-border/40 last:border-0">
                <span className="text-xs text-muted-foreground">Risk</span>
                <span
                  className={cn(
                    "inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide border",
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
