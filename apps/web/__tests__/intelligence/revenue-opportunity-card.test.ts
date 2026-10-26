import { describe, expect, it } from "vitest"
import { formatMoneyCompact, revenueOpportunityCard } from "@/components/intelligence/overview/overview-model"
import type { RevenueOpportunities } from "@/lib/api"

const routes = { connectors: "/connectors" }

function data(overrides: Partial<RevenueOpportunities>): RevenueOpportunities {
  return {
    status: "ready",
    error: null,
    lookaheadDays: 90,
    method: "",
    total: 124800,
    currency: "USD",
    count: 2,
    rows: [],
    moreCount: 0,
    otherCurrencies: {},
    unpricedCount: 0,
    toCollect: null,
    generatedAt: "2026-10-26T00:00:00Z",
    ...overrides,
  }
}

describe("Revenue opportunities card", () => {
  it("shows the CRM total and opens the deals behind it", () => {
    const card = revenueOpportunityCard(data({}), routes)
    expect(card.label).toBe("Revenue opportunities")
    expect(card.value).toBe(124800)
    expect(card.certainty).toBe("measured")
    expect(card.evidence).toBe(true)
    expect(card.link.label).toBe("Based on 2 deals")
    expect(formatMoneyCompact(124800, "USD")).toBe("$124.8K")
  })

  it("never turns a missing CRM into zero", () => {
    const card = revenueOpportunityCard(data({ status: "not_connected", total: null, count: 0 }), routes)
    expect(card.value).toBeNull()
    expect(card.link).toEqual({ label: "Connect HubSpot", href: "/connectors" })
    expect(card.evidence).toBeUndefined()
    expect(revenueOpportunityCard(undefined, routes).value).toBeNull()
  })

  it("says when open deals have no amount", () => {
    const card = revenueOpportunityCard(data({ total: null, count: 0, unpricedCount: 3 }), routes)
    expect(card.value).toBeNull()
    expect(card.hint).toContain("none has an amount")
  })
})
