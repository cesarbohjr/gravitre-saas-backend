import { describe, expect, it } from "vitest"
import { modelBusinessLabel } from "@/lib/intelligence/business-labels"

describe("modelBusinessLabel", () => {
  it("maps known slugs to business labels", () => {
    expect(modelBusinessLabel("intent_classifier")).toBe("Intent Understanding")
    expect(modelBusinessLabel("churn_risk_scorer")).toBe("Customer Churn Risk")
  })

  it("title-cases unknown slugs instead of showing raw snake_case", () => {
    expect(modelBusinessLabel("custom_risk_model")).toBe("Custom Risk Model")
  })
})
