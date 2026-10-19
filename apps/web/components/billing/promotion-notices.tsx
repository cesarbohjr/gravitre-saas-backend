"use client"

import useSWR from "swr"
import { BadgePercent, Gift } from "lucide-react"
import { SetNote } from "@/components/settings/settings-kit"
import { discountEndsLabel, type CurrentPromotions } from "@/lib/promotions"
import { fetchCurrentPromotions } from "@/lib/promotions-api"

export const CURRENT_PROMOTIONS_KEY = "billing-current-promotions"

/** SWR hook shared by the billing notices and the plan picker's promo field. */
export function useCurrentPromotions(enabled: boolean) {
  return useSWR<CurrentPromotions>(enabled ? CURRENT_PROMOTIONS_KEY : null, fetchCurrentPromotions, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
}

/**
 * Settings › Billing: the org's available founder offer ("applied automatically
 * at checkout") and the discount currently on the Stripe subscription.
 * Renders nothing when there is neither, or when the lookup fails.
 */
export function PromotionNotices({ enabled }: { enabled: boolean }) {
  const { data } = useCurrentPromotions(enabled)
  if (!data) return null
  const discount = data.active_discount
  const discountLine = discountEndsLabel(discount)
  return (
    <>
      {data.founder_offer ? (
        <SetNote tone="green" icon={Gift}>
          <span data-testid="founder-offer-banner">
            {data.founder_offer.message}
            {data.founder_offer.valid_until
              ? ` Redeem by ${new Date(data.founder_offer.valid_until).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}.`
              : ""}
            {data.founder_offer.checkout_in_progress ? " A checkout with this offer is already in progress." : ""}
          </span>
        </SetNote>
      ) : null}
      {discount && discountLine ? (
        <SetNote icon={BadgePercent}>
          <span data-testid="active-discount">
            Current discount: <strong>{discountLine}</strong>
            {discount.source === "founder_offer" ? " (founder offer)" : discount.source === "promotion_code" ? " (promo code)" : ""}.
          </span>
        </SetNote>
      ) : null}
    </>
  )
}
