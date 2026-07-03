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
      className="border-b border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-foreground"
      role="alert"
      aria-live="polite"
      data-testid="trial-expired-banner"
    >
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <span>{message}</span>
        {onUpgradeClick ? (
          <Button size="sm" variant="default" onClick={onUpgradeClick}>
            Upgrade now
          </Button>
        ) : (
          <Button size="sm" variant="default" asChild>
            <Link href={upgradeUrl}>Upgrade now</Link>
          </Button>
        )}
      </div>
    </div>
  )
}
