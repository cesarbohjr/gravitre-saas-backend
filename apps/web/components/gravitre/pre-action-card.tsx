"use client"

/**
 * EditTool-inspired write-authority chrome (ADAPT).
 * Same PreActionCard payload + handlers.
 */

import Link from "next/link"
import { Check, Loader2, Pencil, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { RADIUS, TYPE } from "@/lib/design-system"
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
  /** Replaces the action row, e.g. a queued-for-approver status. */
  footer?: React.ReactNode
}

const RISK_LABEL: Record<PreActionRiskLevel, string> = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
}

const RISK_TONE: Record<PreActionRiskLevel, string> = {
  low: "text-[color:var(--g-text-secondary)] bg-muted",
  medium: "text-[color:var(--warning)] bg-[color:var(--warning)]/10",
  high: "text-destructive bg-destructive/10",
}

function sentenceCase(value: string): string {
  const trimmed = value.trim()
  return trimmed ? trimmed.charAt(0).toUpperCase() + trimmed.slice(1) : trimmed
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-4">
      <dt className={cn(TYPE.meta, "shrink-0 sm:w-24")}>{label}</dt>
      <dd className="min-w-0 text-sm text-foreground">{children}</dd>
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
  footer,
}: PreActionCardProps) {
  const modifyHref =
    !onModify && payload.source === "approvals_queue" && payload.conversationId
      ? `/ai?conversation=${encodeURIComponent(payload.conversationId)}`
      : null

  const title =
    variant === "chat"
      ? payload.requiresApproval
        ? "Needs your approval"
        : "Ready to run"
      : "Pre-action review"

  const showAction = Boolean(payload.action && payload.action !== payload.title)
  const hasFacts =
    Boolean(payload.entity) || showAction || Boolean(payload.estimatedImpact) || Boolean(payload.approvalReason)
  const showActions = !hideActions && Boolean(onApprove || onReject || onModify || modifyHref)

  return (
    <div
      className={cn(
        "overflow-hidden border bg-card text-sm",
        RADIUS.card,
        variant === "chat" ? "border-[color:var(--warning)]/35" : "border-border",
        className,
      )}
      data-testid="pre-action-card"
      data-source={payload.source}
      data-risk={payload.riskLevel || ""}
      data-impact={payload.estimatedImpact || ""}
    >
      <div className="flex items-center justify-between gap-3 px-4 pt-3.5">
        <div
          className={cn(
            "flex min-w-0 items-center gap-1.5 text-xs font-medium",
            variant === "chat" ? "text-[color:var(--warning)]" : "text-muted-foreground",
          )}
        >
          <NucleoApproval className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="truncate">{title}</span>
        </div>
        {payload.riskLevel ? (
          <span
            className={cn(
              "inline-flex shrink-0 items-center rounded-[4px] px-1.5 py-0.5 text-xs font-medium",
              RISK_TONE[payload.riskLevel],
            )}
          >
            {RISK_LABEL[payload.riskLevel]}
          </span>
        ) : null}
      </div>

      <div className="flex min-w-0 flex-col gap-1 px-4 pt-2">
        <p className="text-[15px] font-medium leading-snug text-foreground text-pretty">{payload.title}</p>
        {payload.description ? (
          <p className="text-sm leading-relaxed text-muted-foreground text-pretty">{payload.description}</p>
        ) : null}
      </div>

      {hasFacts ? (
        <dl className="mx-4 mt-3 flex flex-col gap-2 border-t border-border/60 pt-3" data-testid="pre-action-explain">
          {payload.entity ? <Fact label="Where">{sentenceCase(payload.entity)}</Fact> : null}
          {payload.estimatedImpact ? <Fact label="Changes">{payload.estimatedImpact}</Fact> : null}
          {payload.approvalReason ? <Fact label="Why">{sentenceCase(payload.approvalReason)}</Fact> : null}
          {showAction ? (
            <Fact label="Action">
              <code className="break-all font-mono text-xs text-muted-foreground">{payload.action}</code>
            </Fact>
          ) : null}
        </dl>
      ) : null}

      {footer ? (
        <div className="mt-3.5 border-t border-border/60 px-4 py-3">{footer}</div>
      ) : showActions ? (
        <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-border/60 px-4 py-3">
          {onApprove ? (
            <Button size="sm" className="h-8" disabled={confirming} onClick={onApprove}>
              {confirming ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Check className="h-3.5 w-3.5" aria-hidden />
              )}
              {approveLabel || (confirming ? "Approving…" : "Approve")}
            </Button>
          ) : null}
          {onModify ? (
            <Button size="sm" variant="outline" className="h-8" disabled={confirming} onClick={onModify}>
              <Pencil className="h-3.5 w-3.5" aria-hidden />
              Modify
            </Button>
          ) : null}
          {modifyHref ? (
            <Button size="sm" variant="outline" className="h-8" asChild>
              <Link href={modifyHref}>
                <Pencil className="h-3.5 w-3.5" aria-hidden />
                Modify
              </Link>
            </Button>
          ) : null}
          {onReject ? (
            <Button
              size="sm"
              variant="ghost"
              className="h-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              disabled={confirming}
              onClick={onReject}
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              Reject
            </Button>
          ) : null}
          {payload.modifyHint && (onModify || modifyHref) ? (
            <p className="ml-auto text-xs text-muted-foreground">{payload.modifyHint}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
