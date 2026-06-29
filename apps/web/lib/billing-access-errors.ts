import { emitPlanRequired, type PlanRequiredDetail } from "@/lib/billing-plan-required"
import { ApiError, PlanRequiredApiError } from "@/lib/fetcher"

export { PlanRequiredApiError } from "@/lib/fetcher"

export function isBillingAccessError(error: unknown): boolean {
  if (error instanceof PlanRequiredApiError) return true
  if (error instanceof ApiError) {
    if (error.status === 402) return true
    if (error.status === 403) {
      const message = error.message.toLowerCase()
      return (
        message.includes("feature unavailable") ||
        message.includes("upgrade required") ||
        message.includes("plan required")
      )
    }
  }
  return false
}

export function billingAccessTitle(error: unknown): string {
  if (error instanceof PlanRequiredApiError) {
    if (error.planDetail.subscription_status === "trial_expired") {
      return "Trial ended"
    }
    return "Subscription required"
  }
  if (error instanceof ApiError && error.status === 403) {
    const message = error.message.toLowerCase()
    if (message.includes("feature unavailable")) {
      return "Plan upgrade required"
    }
  }
  return "Upgrade to continue"
}

export function billingAccessMessage(error: unknown): string {
  if (error instanceof PlanRequiredApiError) {
    return error.message
  }
  if (error instanceof ApiError) {
    if (error.status === 402) {
      return "Upgrade your subscription to load this section."
    }
    if (error.status === 403) {
      const message = error.message.toLowerCase()
      if (message.includes("feature unavailable")) {
        return "This feature needs Control or higher. Upgrade to unlock federation and advanced API access."
      }
      if (message.includes("upgrade required")) {
        return "Your current plan does not include this feature. Upgrade to continue."
      }
    }
  }
  return "Upgrade your plan to continue using this feature."
}

export function openUpgradeModal(detail?: Partial<PlanRequiredDetail>) {
  emitPlanRequired({
    error: "plan_required",
    subscription_status: detail?.subscription_status ?? "trial_expired",
    message: detail?.message ?? "Upgrade to continue using Gravitre.",
    upgrade_url: detail?.upgrade_url ?? "/settings/billing",
  })
}
