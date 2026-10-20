import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  PROMO_STORAGE_KEY,
  describePromoTerms,
  discountEndsLabel,
  discountedMonthlyPrice,
  normalizePromoCode,
  promoAppliesToPlan,
  promoCodeFromSearch,
  promotionValueCents,
  readRememberedPromoCode,
  rememberPromoCode,
  suggestedPromotionCap,
  withPromoParam,
  type PromoValidation,
} from "@/lib/promotions"

class MemoryStorage {
  private values = new Map<string, string>()
  getItem(key: string) {
    return this.values.get(key) ?? null
  }
  setItem(key: string, value: string) {
    this.values.set(key, value)
  }
  removeItem(key: string) {
    this.values.delete(key)
  }
}

const VALID: PromoValidation = {
  valid: true,
  summary: "30% off for 3 months",
  reason: null,
  code: "LAUNCH30",
  percent_off: 30,
  duration: "repeating",
  duration_in_months: 3,
  plan_codes: ["control", "command"],
}

describe("promo code normalization and carry-through", () => {
  const g = globalThis as unknown as { window?: { localStorage: MemoryStorage } }
  beforeEach(() => {
    g.window = { localStorage: new MemoryStorage() }
  })
  afterEach(() => {
    delete g.window
  })

  it("normalizes and rejects unsafe codes", () => {
    expect(normalizePromoCode(" launch30 ")).toBe("LAUNCH30")
    expect(normalizePromoCode("<script>")).toBeNull()
    expect(normalizePromoCode("ab")).toBeNull()
  })

  it("remembers ?promo= and expires it after 14 days", () => {
    expect(promoCodeFromSearch(new URLSearchParams("promo=launch30"))).toBe("LAUNCH30")
    expect(readRememberedPromoCode()).toBe("LAUNCH30")
    expect(readRememberedPromoCode(Date.now() + 15 * 24 * 3600 * 1000)).toBeNull()
    expect(g.window!.localStorage.getItem(PROMO_STORAGE_KEY)).toBeNull()
  })

  it("prefers the query over a remembered code", () => {
    rememberPromoCode("OLDCODE")
    expect(promoCodeFromSearch(new URLSearchParams("plan=node&promo=NEW20"))).toBe("NEW20")
    expect(promoCodeFromSearch(new URLSearchParams("plan=node"))).toBe("NEW20")
  })

  it("adds ?promo to signup and checkout links", () => {
    expect(withPromoParam("/get-started?plan=node&interval=monthly", "launch30")).toBe(
      "/get-started?plan=node&interval=monthly&promo=LAUNCH30",
    )
    expect(withPromoParam("/settings/billing", null)).toBe("/settings/billing")
  })
})

describe("discount display", () => {
  it("matches the backend summary wording", () => {
    expect(describePromoTerms({ percent_off: 30, duration: "repeating", duration_in_months: 3 })).toBe("30% off for 3 months")
    expect(describePromoTerms({ amount_off_cents: 2000, duration: "once" })).toBe("$20 off your first payment")
    expect(describePromoTerms({ percent_off: 10, duration: "forever" })).toBe("10% off every billing period")
  })

  it("computes the discounted monthly price for eligible plans only", () => {
    expect(discountedMonthlyPrice(149, VALID)).toBe(104.3)
    expect(promoAppliesToPlan(VALID, "node")).toBe(false)
    expect(promoAppliesToPlan(VALID, "control")).toBe(true)
    expect(discountedMonthlyPrice(59, { ...VALID, percent_off: null, amount_off_cents: 2000 })).toBe(39)
  })

  it("labels the live Stripe discount with its end date", () => {
    expect(
      discountEndsLabel({
        label: "30% off",
        summary: "30% off for 3 months",
        percent_off: 30,
        amount_off_cents: null,
        currency: null,
        duration: "repeating",
        ends_at: "2027-01-19T12:00:00Z",
        source: "promotion_code",
      }),
    ).toBe("30% off until Jan 19, 2027")
  })
})

describe("founder offer value cap (mirrors backend promotion_value_cents)", () => {
  it("uses the backend formula", () => {
    // 30% × 3 months × $149/month
    expect(promotionValueCents({ offerType: "discount", percentOff: 30, months: 3 }, 14900, "month")).toBe(13410)
    // Annual: one yearly cycle for up to 12 months
    expect(promotionValueCents({ offerType: "discount", percentOff: 30, months: 3 }, 148800, "year")).toBe(44640)
    // Trial: $149 × 30 / 28, rounded up
    expect(promotionValueCents({ offerType: "trial", trialDays: 30 }, 14900, "month")).toBe(15965)
  })

  it("suggests the largest reachable value so checkout is never blocked", () => {
    const discount = suggestedPromotionCap({ offerType: "discount", percentOff: 30, months: 3 })
    expect(discount).toMatchObject({ cents: 104760, plan: "command", interval: "annual" })
    const trial = suggestedPromotionCap({ offerType: "trial", trialDays: 30 })
    expect(trial).toMatchObject({ cents: 37393, plan: "command", interval: "monthly" })
    expect(trial?.explanation).toContain("Command monthly")
  })
})
