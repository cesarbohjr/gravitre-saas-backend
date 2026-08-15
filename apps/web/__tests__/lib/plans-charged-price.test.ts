import { describe, expect, it } from "vitest"
import { formatChargedPlanPriceLabel, getPlan } from "@/lib/plans"

describe("formatChargedPlanPriceLabel", () => {
  it("uses live Stripe cents for grandfathered subscribers", () => {
    const command = getPlan("command")
    expect(formatChargedPlanPriceLabel(command, 29900, "month")).toBe("$299")
  })

  it("falls back to catalog list price when cents are missing", () => {
    const command = getPlan("command")
    expect(formatChargedPlanPriceLabel(command, null, "month")).toBe("$349")
  })

  it("normalizes annual prices to an effective monthly label", () => {
    const command = getPlan("command")
    expect(formatChargedPlanPriceLabel(command, 349200, "year")).toBe("$291")
  })
})
