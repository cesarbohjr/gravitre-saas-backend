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
          "rounded-xl border border-primary/25 bg-primary/5 px-6 py-8 text-center",
          className,
        )}
      >
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
          <Icon name="lock" size="md" className="text-primary" />
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
        "rounded-xl border border-red-500/20 bg-red-500/5 px-6 py-8 text-center",
        className,
      )}
    >
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
        <Icon name="warning" size="md" className="text-red-400" />
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
