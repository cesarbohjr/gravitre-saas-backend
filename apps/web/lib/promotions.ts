/**
 * Promotions: public promo codes (anyone, at checkout) and founder offers (one
 * org, applied automatically). Pure helpers only — network calls live in
 * `lib/promotions-api.ts` so these stay unit-testable.
 *
 * Rules mirrored from backend/app/billing/promotion_codes.py:
 * - A founder offer always wins; a promo code is never combined with it.
 * - Stripe is authoritative; a code shown as valid here is re-validated at checkout.
 */
import type { BillingInterval, PlanCode } from "@/lib/plans"
import { PLAN_CATALOG } from "@/lib/plans"

export type PromoValidation = {
  valid: boolean
  summary: string | null
  reason: string | null
  code?: string
  percent_off?: number | null
  amount_off_cents?: number | null
  currency?: string | null
  duration?: "once" | "repeating" | "forever" | null
  duration_in_months?: number | null
  plan_codes?: PlanCode[]
  first_time_only?: boolean
  expires_at?: string | null
}

export type FounderOfferView = {
  offer_type: "trial" | "discount"
  trial_days: number | null
  percent_off: number | null
  discount_months: number | null
  valid_until: string | null
  checkout_in_progress: boolean
  summary: string
  message: string
}

export type ActiveDiscountView = {
  label: string
  summary: string
  percent_off: number | null
  amount_off_cents: number | null
  currency: string | null
  duration: string | null
  ends_at: string | null
  source: "promotion_code" | "founder_offer" | "coupon"
}

export type CurrentPromotions = {
  founder_offer: FounderOfferView | null
  active_discount: ActiveDiscountView | null
  discount_unverified: boolean
  promotion_codes_enabled: boolean
}

const CODE_PATTERN = /^[A-Z0-9][A-Z0-9_-]{2,39}$/

export function normalizePromoCode(value: string | null | undefined): string | null {
  const code = (value ?? "").trim().toUpperCase()
  return CODE_PATTERN.test(code) ? code : null
}

// ---------------------------------------------------------------------------
// Carry ?promo=CODE from pricing/signup through to checkout.
// localStorage (not sessionStorage) so the code survives the email-confirmation
// tab; it is not a secret, expires after 14 days, and every access is guarded.
// ---------------------------------------------------------------------------

export const PROMO_STORAGE_KEY = "gravitre-promo-code"
const PROMO_TTL_MS = 14 * 24 * 60 * 60 * 1000

type StoredPromo = { code: string; savedAt: number }

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null
  } catch {
    return null
  }
}

export function rememberPromoCode(value: string | null | undefined, now = Date.now()): string | null {
  const code = normalizePromoCode(value)
  if (!code) return null
  try {
    storage()?.setItem(PROMO_STORAGE_KEY, JSON.stringify({ code, savedAt: now } satisfies StoredPromo))
  } catch {
    // Storage blocked (private mode): the ?promo query still carries it.
  }
  return code
}

export function readRememberedPromoCode(now = Date.now()): string | null {
  try {
    const raw = storage()?.getItem(PROMO_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredPromo>
    const code = normalizePromoCode(parsed.code)
    if (!code || typeof parsed.savedAt !== "number" || now - parsed.savedAt > PROMO_TTL_MS) {
      storage()?.removeItem(PROMO_STORAGE_KEY)
      return null
    }
    return code
  } catch {
    return null
  }
}

export function forgetPromoCode(): void {
  try {
    storage()?.removeItem(PROMO_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/** ?promo=CODE (or ?code=) wins over a remembered code; remembers it. */
export function promoCodeFromSearch(params: { get(name: string): string | null } | null | undefined): string | null {
  const fromQuery = normalizePromoCode(params?.get("promo") ?? params?.get("promo_code") ?? null)
  if (fromQuery) return rememberPromoCode(fromQuery)
  return readRememberedPromoCode()
}

export function withPromoParam(href: string, code: string | null | undefined): string {
  const promo = normalizePromoCode(code)
  if (!promo) return href
  const [path, query = ""] = href.split("?")
  const params = new URLSearchParams(query)
  params.set("promo", promo)
  return `${path}?${params.toString()}`
}

/** Same wording as backend describe_discount(), e.g. "30% off for 3 months". */
export function describePromoTerms(terms: {
  percent_off?: number | null
  amount_off_cents?: number | null
  duration?: "once" | "repeating" | "forever" | null
  duration_in_months?: number | null
}): string {
  let value: string
  if (terms.percent_off) value = `${Number(terms.percent_off)}% off`
  else if (terms.amount_off_cents) value = `${formatUsd(terms.amount_off_cents / 100)} off`
  else return "Discount"
  if (terms.duration === "once") return `${value} your first payment`
  if (terms.duration === "forever") return `${value} every billing period`
  const months = terms.duration_in_months ?? 0
  return months ? `${value} for ${months} month${months === 1 ? "" : "s"}` : value
}

// ---------------------------------------------------------------------------
// Pricing math (display only; Stripe computes the real invoice)
// ---------------------------------------------------------------------------

/** Discounted per-month price for the first discounted period, or null. */
export function discountedMonthlyPrice(price: number | null, promo: PromoValidation | null): number | null {
  if (price === null || price <= 0 || !promo?.valid) return null
  if (promo.percent_off) return Math.max(0, Math.round(price * (100 - promo.percent_off)) / 100)
  if (promo.amount_off_cents) return Math.max(0, Math.round(price * 100 - promo.amount_off_cents) / 100)
  return null
}

export function promoAppliesToPlan(promo: PromoValidation | null, plan: PlanCode): boolean {
  if (!promo?.valid) return false
  return !promo.plan_codes?.length || promo.plan_codes.includes(plan)
}

export function formatUsd(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`
}

export function discountEndsLabel(discount: ActiveDiscountView | null, locale?: string): string | null {
  if (!discount) return null
  if (!discount.ends_at) {
    return discount.duration === "forever" ? `${discount.label} on every invoice` : discount.summary
  }
  const date = new Date(discount.ends_at)
  if (Number.isNaN(date.getTime())) return discount.summary
  const formatted = date.toLocaleDateString(locale ?? "en-US", { month: "short", day: "numeric", year: "numeric" })
  return `${discount.label} until ${formatted}`
}

// ---------------------------------------------------------------------------
// Founder offer value cap — mirrors backend/app/billing/safety.py
// promotion_value_cents(): trial = amount × days / (28 monthly | 365 annual);
// discount = amount × cycles × percent, cycles = months (monthly) or
// ceil(months / 12) (annual). Always rounded up to the cent.
// ---------------------------------------------------------------------------

export type CapInput =
  | { offerType: "trial"; trialDays: number }
  | { offerType: "discount"; percentOff: number; months: number }

export function promotionValueCents(
  input: CapInput,
  unitAmountCents: number,
  interval: "month" | "year",
): number {
  if (!(unitAmountCents > 0)) return 0
  if (input.offerType === "trial") {
    return Math.ceil((unitAmountCents * input.trialDays) / (interval === "month" ? 28 : 365))
  }
  const cycles = interval === "year" ? Math.ceil(input.months / 12) : input.months
  return Math.ceil((unitAmountCents * cycles * input.percentOff) / 100)
}

export type CapSuggestion = {
  cents: number
  plan: PlanCode
  interval: BillingInterval
  basisCents: number
  explanation: string
}

/**
 * Smallest cap that still lets the customer check out on any self-serve plan
 * and interval (the backend blocks checkout above the cap).
 */
export function suggestedPromotionCap(input: CapInput, plans: PlanCode[] = ["node", "control", "command"]): CapSuggestion | null {
  let best: CapSuggestion | null = null
  for (const code of plans) {
    const plan = PLAN_CATALOG[code]
    if (!plan || plan.price === null || plan.annualPrice === null) continue
    const options: { interval: BillingInterval; unit: number; stripe: "month" | "year" }[] = [
      { interval: "monthly", unit: Math.round(plan.price * 100), stripe: "month" },
      { interval: "annual", unit: Math.round(plan.annualPrice * 12 * 100), stripe: "year" },
    ]
    for (const option of options) {
      const cents = promotionValueCents(input, option.unit, option.stripe)
      if (!best || cents > best.cents) {
        const terms =
          input.offerType === "trial"
            ? `${input.trialDays} days of ${formatUsd(option.unit / 100)}/${option.stripe}`
            : `${input.percentOff}% of ${formatUsd(option.unit / 100)}/${option.stripe} × ${
                option.stripe === "year" ? Math.ceil(input.months / 12) : input.months
              }`
        best = {
          cents,
          plan: code,
          interval: option.interval,
          basisCents: option.unit,
          explanation: `Covers ${plan.name} ${option.interval} (${terms}).`,
        }
      }
    }
  }
  return best
}
