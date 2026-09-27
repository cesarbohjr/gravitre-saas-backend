import { describe, expect, it } from "vitest"
import { buildDeliverables } from "@/lib/agent-job-result"

describe("buildDeliverables confidence honesty", () => {
  it("reports the handoff confidence as a percent on the primary answer only", () => {
    const items = buildDeliverables({
      answer: "Quarterly pipeline summary",
      confidence: 0.82,
      recommended_actions: ["Email the account owner", "Open a follow-up task"],
    })
    expect(items[0]).toMatchObject({ id: "primary-answer", confidence: 82 })
    expect(items.filter((item) => item.id.startsWith("action-")).map((item) => item.confidence)).toEqual([0, 0])
  })

  it("leaves confidence unreported (0) when the handoff omits it", () => {
    const [primary] = buildDeliverables({ answer: "Done" })
    expect(primary.confidence).toBe(0)
  })
})
