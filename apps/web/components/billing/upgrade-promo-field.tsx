"use client"

import { useState } from "react"
import { useSearchParams } from "next/navigation"
import { PromoCodeField, type AppliedPromo } from "@/components/billing/promo-code-field"
import { useCurrentPromotions } from "@/components/billing/promotion-notices"
import { promoCodeFromSearch } from "@/lib/promotions"

/**
 * Promo field for the in-app plan picker. Prefills ?promo= or a code carried
 * from pricing/signup; replaced by a note when a founder offer applies (the
 * offer wins and codes are never combined with it).
 */
export function UpgradePromoField({
  plan,
  onApplied,
}: {
  plan: string | null
  onApplied: (applied: AppliedPromo | null) => void
}) {
  const searchParams = useSearchParams()
  const [initialCode] = useState(() => promoCodeFromSearch(searchParams))
  const { data } = useCurrentPromotions(true)
  const founder = data?.founder_offer
  const disabled = data && !data.promotion_codes_enabled
  if (disabled) return null
  return (
    <PromoCodeField
      plan={plan}
      initialCode={initialCode}
      onApplied={onApplied}
      blockedReason={
        founder
          ? `Your founder offer (${founder.summary}) is applied automatically at checkout. Promo codes can't be combined with it.`
          : null
      }
    />
  )
}
