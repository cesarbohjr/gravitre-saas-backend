"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"

interface TrialExpiredBannerProps {
  message?: string
  upgradeUrl?: string
  onUpgradeClick?: () => void
}

export function TrialExpiredBanner({
  message = "Your 7-day trial has ended. Upgrade to continue using Gravitre.",
  upgradeUrl = "/settings/billing",
  onUpgradeClick,
}: TrialExpiredBannerProps) {
  return (
    <div
      className="flex min-h-9 items-center gap-3 border-b border-l-2 border-[color:var(--g-border-subtle)] border-l-destructive bg-background px-4 py-1.5 text-[13px] text-foreground"
      role="alert"
      aria-live="polite"
      data-testid="trial-expired-banner"
    >
      <span className="min-w-0 flex-1 truncate">{message}</span>
      {onUpgradeClick ? (
        <Button size="sm" variant="default" className="h-7 shrink-0 rounded-[4px] px-3 text-xs" onClick={onUpgradeClick}>
          Upgrade now
        </Button>
      ) : (
        <Button size="sm" variant="default" className="h-7 shrink-0 rounded-[4px] px-3 text-xs" asChild>
          <Link href={upgradeUrl}>Upgrade now</Link>
        </Button>
      )}
    </div>
  )
}
