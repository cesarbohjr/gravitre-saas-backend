"use client"

import { cn } from "@/lib/utils"
import { EnvironmentBadge } from "./environment-badge"
import { StatusBadge } from "./status-badge"
import { Icon, type IconName } from "@/lib/icons"
import { Button } from "@/components/ui/button"

interface TrustBadges {
  confidenceScore: number // 0-100
  guardrailStatus: "pass" | "warn" | "fail"
  tokenCount: number
  approvalRequired: boolean
}

interface ActionProposalProps {
  title: string
  description?: string
  icon: IconName
  environment: "production" | "staging"
  trustBadges: TrustBadges
  onApprove?: () => void
  onReject?: () => void
  onModify?: () => void
  className?: string
}

export function ActionProposal({
  title,
  description,
  icon,
  environment,
  trustBadges,
  onApprove,
  onReject,
  onModify,
  className,
}: ActionProposalProps) {
  const { confidenceScore, guardrailStatus, tokenCount, approvalRequired } = trustBadges

  const confidenceVariant = confidenceScore >= 80 ? "success" : confidenceScore >= 50 ? "warning" : "error"
  const guardrailVariant = guardrailStatus === "pass" ? "success" : guardrailStatus === "warn" ? "warning" : "error"
  const guardrailIcon: IconName = guardrailStatus === "pass" ? "success" : guardrailStatus === "warn" ? "warning" : "failed"

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-4",
        className
      )}
    >
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary">
            <Icon name={icon} size="lg" className="text-foreground" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-foreground">{title}</h3>
            {description && (
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">{description}</p>
            )}
          </div>
        </div>
        <EnvironmentBadge environment={environment} />
      </div>

      {/* Trust Badges - 4 required badges */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {/* Accuracy */}
        <StatusBadge variant={confidenceVariant} className="gap-1.5">
          <Icon name="confidence" size="xs" />
          <span>{confidenceScore}% sure</span>
        </StatusBadge>

        {/* Safety Check */}
        <StatusBadge variant={guardrailVariant} className="gap-1.5">
          <Icon name={guardrailIcon} size="xs" emphasis />
          <span className="capitalize">{guardrailStatus === "pass" ? "Safe" : guardrailStatus === "warn" ? "Review Needed" : "Blocked"}</span>
        </StatusBadge>

        {/* Usage */}
        <StatusBadge variant="muted" className="gap-1.5">
          <Icon name="gauge" size="xs" />
          <span>{tokenCount.toLocaleString()} used</span>
        </StatusBadge>

        {/* Approval */}
        <StatusBadge variant={approvalRequired ? "warning" : "success"} className="gap-1.5">
          <Icon name="shield" size="xs" />
          <span>{approvalRequired ? "Needs Approval" : "Auto-approved"}</span>
        </StatusBadge>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          className="h-8 gap-1.5 bg-success/20 text-success hover:bg-success/30"
          onClick={onApprove}
        >
          <Icon name="success" size="sm" />
          Approve
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-8 gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={onReject}
        >
          <Icon name="failed" size="sm" />
          Reject
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-8 text-muted-foreground hover:text-foreground"
          onClick={onModify}
        >
          Modify
        </Button>
      </div>
    </div>
  )
}
