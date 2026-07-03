import type { PlanRequiredDetail } from "@/lib/billing-plan-required"

export type BillingStatusSnapshot = {
  billingStatus?: string
  planCode?: string
  canAccessApp?: boolean | null
  requiresUpgrade?: boolean
  upgradeReason?: string | null
  trialEndsAt?: string | null
  trialExpired?: boolean
  billingState?: string
  billingKnown?: boolean
  _auth_degraded?: boolean
}

export function isBillingStatusDegraded(status?: BillingStatusSnapshot | null): boolean {
  return status?._auth_degraded === true || status?.billingKnown === false
}

export function isTrialExpiredFromBillingStatus(status?: BillingStatusSnapshot | null): boolean {
  if (!status || isBillingStatusDegraded(status)) return false
  return (
    status.trialExpired === true ||
    status.billingState === "trial_expired" ||
    status.upgradeReason === "trial_expired" ||
    (status.canAccessApp === false && status.upgradeReason === "trial_expired")
  )
}

export function isTrialExpiredFromPlanRequired(detail?: PlanRequiredDetail | null): boolean {
  return detail?.error === "plan_required" && detail.subscription_status === "trial_expired"
}

export function isTrialExpiredState(
  status?: BillingStatusSnapshot | null,
  planRequired?: PlanRequiredDetail | null,
): boolean {
  return isTrialExpiredFromPlanRequired(planRequired) || isTrialExpiredFromBillingStatus(status)
}

export function resolveCanAccessApp(
  status?: BillingStatusSnapshot | null,
  meCanAccess?: boolean | null,
  planRequired?: PlanRequiredDetail | null,
): boolean {
  if (isTrialExpiredState(status, planRequired)) return false
  if (status?.canAccessApp === true) return true
  if (status?.canAccessApp === false) return false
  if (isBillingStatusDegraded(status)) {
    return !isTrialExpiredFromPlanRequired(planRequired)
  }
  if (meCanAccess === true) return true
  if (meCanAccess === false) return false
  return true
}

export function trialExpiredBannerMessage(planRequired?: PlanRequiredDetail | null): string {
  return (
    planRequired?.message?.trim() ||
    "Your 7-day trial has ended. Upgrade to continue using Gravitre."
  )
}
