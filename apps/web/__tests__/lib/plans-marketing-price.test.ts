import { describe, expect, it } from "vitest"
import { formatMarketingPlanPriceLabel, getPlan, PLAN_CATALOG } from "@/lib/plans"
import { tiers } from "@/lib/pricing-page-data"

describe("marketing plan prices", () => {
  it("PLAN_CATALOG matches public pricing page tiers", () => {
    for (const tier of tiers) {
      const plan = getPlan(tier.planCode)
      expect(plan.price).toBe(tier.price.monthly)
      expect(formatMarketingPlanPriceLabel(plan)).toBe(`$${tier.price.monthly}`)
    }
  })

  it("uses current voice-included list prices (not legacy Stripe amounts)", () => {
    expect(PLAN_CATALOG.node.price).toBe(59)
    expect(PLAN_CATALOG.control.price).toBe(149)
    expect(PLAN_CATALOG.command.price).toBe(349)
    expect(formatMarketingPlanPriceLabel(getPlan("command"))).toBe("$349")
  })
})
