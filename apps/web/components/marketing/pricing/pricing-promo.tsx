"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { BadgePercent } from "lucide-react"
import { Container } from "@/components/marketing/nodus/container"
import { PLAN_CATALOG, SELECTABLE_PLANS } from "@/lib/plans"
import {
  discountedMonthlyPrice,
  formatUsd,
  promoAppliesToPlan,
  promoCodeFromSearch,
  type PromoValidation,
} from "@/lib/promotions"
import { validatePromoCode } from "@/lib/promotions-api"

type PricingPromo = { code: string; validation: PromoValidation } | null

const PricingPromoContext = createContext<PricingPromo>(null)

/**
 * Reads ?promo=CODE (or a code remembered from an earlier visit) on the client,
 * validates it, and shares the result with the plan cards and banner. Reading
 * `window.location` in an effect keeps /pricing statically renderable.
 */
export function PricingPromoProvider({ children }: { children: ReactNode }) {
  const [promo, setPromo] = useState<PricingPromo>(null)
  useEffect(() => {
    const code = promoCodeFromSearch(new URLSearchParams(window.location.search))
    if (!code) return
    let cancelled = false
    void validatePromoCode(code).then((validation) => {
      if (!cancelled && validation.valid) setPromo({ code, validation })
    })
    return () => {
      cancelled = true
    }
  }, [])
  return <PricingPromoContext.Provider value={promo}>{children}</PricingPromoContext.Provider>
}

export function usePricingPromo(): PricingPromo {
  return useContext(PricingPromoContext)
}

/** Small banner above the plans when a valid ?promo= code is present. */
export function PricingPromoBanner() {
  const promo = usePricingPromo()
  if (!promo) return null
  const { code, validation } = promo
  const examples = SELECTABLE_PLANS.filter((plan) => promoAppliesToPlan(validation, plan.code))
    .map((plan) => {
      const now = discountedMonthlyPrice(plan.price, validation)
      return now === null ? null : `${plan.name} ${formatUsd(plan.price ?? 0)} → ${formatUsd(now)}/mo`
    })
    .filter(Boolean)
  return (
    <Container className="border-divide border-x px-4 pt-6 md:px-8">
      <div
        role="status"
        className="mx-auto flex max-w-3xl items-start gap-3 rounded-xl border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-charcoal-700"
        data-testid="pricing-promo-banner"
      >
        <BadgePercent className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden />
        <p>
          <strong className="font-mono">{code}</strong>: {validation.summary}. It&apos;s applied when you upgrade.
          {examples.length ? <span className="mt-1 block text-xs text-gray-600">{examples.join(" · ")}</span> : null}
        </p>
      </div>
    </Container>
  )
}

/** Discounted monthly price for a tier card, when the active code applies to it. */
export function usePromoPriceFor(planCode: keyof typeof PLAN_CATALOG, price: number): number | null {
  const promo = usePricingPromo()
  if (!promo || !promoAppliesToPlan(promo.validation, planCode)) return null
  return discountedMonthlyPrice(price, promo.validation)
}
