import { describe, expect, it } from "vitest"
import type { BillingUsageResponse } from "@/types/api"
import {
  autoRenewLine,
  cardExpiry,
  cardTitle,
  defaultPaymentMethod,
  invoiceRows,
  planPriceLabel,
  renewalLine,
  subscriptionStatus,
  usageBarWidth,
  usageTiles,
} from "@/lib/settings-api/billing"

const usage = (over: Partial<BillingUsageResponse> = {}): BillingUsageResponse => ({
  period_start: "2026-10-01T00:00:00Z",
  tier: "command",
  totals: { outputs: 3, workflow_runs: 9000, api_calls: 120, ai_tokens: 0, research_lookups: 22, voice_minutes: 0 },
  included_outputs: 120,
  workflow_runs_included: 10000,
  ai_credits_included: 15000,
  overage_outputs: 0,
  overage_cost_usd: 0,
  ...over,
})

describe("Billing usage tiles", () => {
  it("uses real allowances and marks the tone by percent", () => {
    const tiles = usageTiles(usage(), "command")
    const runs = tiles.find((t) => t.key === "workflow_runs")!
    expect(runs).toMatchObject({ used: 9000, limit: 10000, pct: 90, tone: "red" })
    expect(tiles.map((t) => t.key)).toEqual(["workflow_runs", "ai_credits", "outputs", "api_calls"])
  })

  it("only shows research lookups and voice minutes when billing makes them visible", () => {
    const keys = usageTiles(
      usage({ research_lookups_billing_visible: true, included_research_lookups: 200, voice_minutes_billing_visible: true }),
      "command",
    ).map((t) => t.key)
    expect(keys).toContain("research_lookups")
    expect(keys).toContain("voice_minutes")
  })

  it("never invents a cap: no allowance anywhere means metered", () => {
    const tiles = usageTiles(usage({ tier: "enterprise", workflow_runs_included: 0, ai_credits_included: 0, included_outputs: null }), "enterprise")
    for (const key of ["workflow_runs", "ai_credits", "outputs", "api_calls"]) {
      const t = tiles.find((x) => x.key === key)!
      expect(t.limit).toBeNull()
      expect(t.pct).toBeNull()
      expect(usageBarWidth(t)).toBe("0%")
    }
  })

  it("returns nothing before the overview loads", () => {
    expect(usageTiles(undefined, "command")).toEqual([])
  })
})

describe("Billing plan card", () => {
  it("prefers the live Stripe price and its interval", () => {
    expect(planPriceLabel({ unitAmountCents: 29900, interval: "month", catalogPrice: "$349", catalogMonthly: true })).toMatchObject({
      period: "/ month",
    })
    expect(planPriceLabel({ unitAmountCents: 349200, interval: "year", catalogPrice: "$349" })?.period).toBe("/ year")
    expect(planPriceLabel({ unitAmountCents: null, catalogPrice: "$349", catalogMonthly: true })).toEqual({ amount: "$349", period: "/ month" })
    expect(planPriceLabel({ unitAmountCents: null, catalogPrice: "Custom", catalogMonthly: false })).toEqual({ amount: "Custom", period: null })
  })

  it("states renewal, trial end and access end from the period end", () => {
    expect(renewalLine("active", "2026-11-17T12:00:00Z", false)).toMatch(/^Renews /)
    expect(renewalLine("trialing", "2026-11-17T12:00:00Z", false)).toMatch(/^Trial ends /)
    expect(renewalLine("active", "2026-11-17T12:00:00Z", true)).toMatch(/^Access ends /)
    expect(renewalLine("active", null, false)).toBeNull()
    expect(autoRenewLine(true, "2026-11-17T12:00:00Z")).toMatch(/^Renews automatically on /)
    expect(autoRenewLine(false, null)).toBe("Auto renew is off")
  })

  it("normalizes the cancelled spelling and prefers the subscription status", () => {
    expect(subscriptionStatus({ billing_status: "cancelled" } as never)).toBe("canceled")
    expect(subscriptionStatus(undefined)).toBe("unknown")
  })
})

describe("Invoices and payment method", () => {
  it("maps Stripe invoices with number, status tone and a download link", () => {
    const [row] = invoiceRows([
      {
        id: "in_1",
        number: "INV-0001",
        amount_cents: 34900,
        currency: "usd",
        status: "paid",
        period_start: "2026-09-17T12:00:00Z",
        period_end: "2026-10-17T12:00:00Z",
        created_at: "2026-10-17T12:00:00Z",
        hosted_invoice_url: "https://invoice.stripe.com/i/1",
      },
    ])
    expect(row).toMatchObject({ number: "INV-0001", status: "Paid", tone: "green", downloadUrl: "https://invoice.stripe.com/i/1" })
    expect(row.amount).toContain("349")
  })

  it("shows the default card with brand, last 4 and expiry, or nothing", () => {
    expect(defaultPaymentMethod([])).toBeNull()
    const card = defaultPaymentMethod([
      { id: "pm_2", type: "card", last4: "1111", exp_month: 1, exp_year: 2027, is_default: false },
      { id: "pm_1", type: "card", brand: "visa", last4: "4242", exp_month: 8, exp_year: 2028, is_default: true } as never,
    ])!
    expect(card.id).toBe("pm_1")
    expect(cardTitle(card)).toBe("Visa ending 4242")
    expect(cardExpiry(card)).toBe("Expires 08/2028")
    expect(cardTitle({ id: "x", type: "card", last4: null, exp_month: 0, exp_year: 0, is_default: false } as never)).toBe("Card")
  })
})
