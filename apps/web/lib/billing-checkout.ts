import { billingApi, ApiRequestError } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import type { BillingInterval, PlanCode } from "@/lib/plans"

export type PlanCheckoutResult =
  | { mode: "payment_element"; clientSecret: string }
  | { mode: "redirect"; url: string }

/**
 * Start paid plan checkout for the current org. Resolves org context first, then
 * prefers in-app Payment Element; falls back to Stripe hosted checkout on failure.
 */
export async function startPlanCheckout(
  planCode: PlanCode,
  billingInterval: BillingInterval = "monthly",
): Promise<PlanCheckoutResult> {
  const orgId = await ensureSelectedOrg(true)
  if (!orgId) {
    throw new Error("Could not resolve your organization. Refresh the page and try again.")
  }

  try {
    const response = await billingApi.createSubscriptionForPlan(planCode, billingInterval)
    if (!response.client_secret?.trim()) {
      throw new Error("Checkout could not be prepared. Please try again.")
    }
    return { mode: "payment_element", clientSecret: response.client_secret }
  } catch (primaryError) {
    try {
      const checkout = await billingApi.createCheckoutForPlan(planCode, billingInterval)
      if (checkout.checkout_url?.trim()) {
        return { mode: "redirect", url: checkout.checkout_url }
      }
    } catch {
      // Prefer the primary error when hosted checkout also fails.
    }

    if (primaryError instanceof ApiRequestError) {
      throw primaryError
    }
    if (primaryError instanceof Error && primaryError.message.trim()) {
      throw primaryError
    }
    throw new Error("Could not start checkout. Please try again.")
  }
}
