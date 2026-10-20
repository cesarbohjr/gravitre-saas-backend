import { billingApi, ApiRequestError, type CheckoutDiscountFields } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import type { BillingInterval, PlanCode } from "@/lib/plans"

export type PlanCheckoutResult =
  | ({ mode: "payment_element"; clientSecret: string } & CheckoutDiscountFields)
  | ({ mode: "redirect"; url: string } & CheckoutDiscountFields)

/**
 * Start paid plan checkout for the current org. Resolves org context first, then
 * prefers in-app Payment Element; falls back to Stripe hosted checkout on failure
 * (including 409 for founder-offer holders — their offer is applied there and a
 * promo code is ignored, never combined).
 *
 * `promotionCode` is optional; the backend validates it and Stripe re-validates.
 * Without a code, hosted checkout shows Stripe's own promo-code field.
 */
export async function startPlanCheckout(
  planCode: PlanCode,
  billingInterval: BillingInterval = "monthly",
  promotionCode?: string | null,
): Promise<PlanCheckoutResult> {
  const orgId = await ensureSelectedOrg(true)
  if (!orgId) {
    throw new Error("Could not resolve your organization. Refresh the page and try again.")
  }

  try {
    const response = await billingApi.createSubscriptionForPlan(planCode, billingInterval, promotionCode)
    if (!response.client_secret?.trim()) {
      throw new Error("Checkout could not be prepared. Please try again.")
    }
    return { ...pickDiscount(response), mode: "payment_element", clientSecret: response.client_secret }
  } catch (primaryError) {
    // An invalid promo code fails the same way on hosted checkout; surface it.
    if (primaryError instanceof ApiRequestError && primaryError.status === 422 && promotionCode) {
      throw primaryError
    }
    try {
      const checkout = await billingApi.createCheckoutForPlan(planCode, billingInterval, promotionCode)
      if (checkout.checkout_url?.trim()) {
        return { ...pickDiscount(checkout), mode: "redirect", url: checkout.checkout_url }
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

function pickDiscount(source: CheckoutDiscountFields): CheckoutDiscountFields {
  const { discount_source, promotion_code, discount_summary, promotion_code_ignored, notice } = source
  return { discount_source, promotion_code, discount_summary, promotion_code_ignored, notice }
}
