"use client"

import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import {
  billingAccessMessage,
  billingAccessTitle,
  isBillingAccessError,
  openUpgradeModal,
} from "@/lib/billing-access-errors"
import { cn } from "@/lib/utils"

export function WorkSectionErrorCard({
  title = "Something went wrong",
  message = "We couldn't load this section. Please try again.",
  error,
  onRetry,
  onUpgrade,
  className,
}: {
  title?: string
  message?: string
  error?: unknown
  onRetry?: () => void
  onUpgrade?: () => void
  className?: string
}) {
  const billingBlocked = error ? isBillingAccessError(error) : false

  if (billingBlocked) {
    return (
      <div
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] px-6 py-8 text-center shadow-[var(--np-shadow)]",
          className,
        )}
      >
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[color:var(--g-brand)]/15">
          <Icon name="lock" size="md" className="text-[color:var(--g-brand)]" />
        </div>
        <p className="text-sm font-medium text-foreground">{billingAccessTitle(error)}</p>
        <p className="mt-1 text-xs text-muted-foreground">{billingAccessMessage(error)}</p>
        <Button
          size="sm"
          className="mt-4"
          onClick={() => {
            if (onUpgrade) {
              onUpgrade()
              return
            }
            openUpgradeModal()
          }}
        >
          View plans
        </Button>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-destructive/25 bg-destructive/5 px-6 py-8 text-center shadow-[var(--np-shadow)]",
        className,
      )}
    >
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
        <Icon name="warning" size="md" className="text-destructive" />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-4" onClick={() => onRetry()}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}
