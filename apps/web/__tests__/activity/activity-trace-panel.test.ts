import { describe, expect, it } from "vitest"
import {
  buildActivityTraceStages,
} from "@/components/activity/activity-trace-panel"
import type { BusinessOutcomeDto } from "@/components/gravitre/business-outcome/business-outcome-view"

describe("Activity A1 TRACE builder", () => {
  it("builds stages from real timeline without inventing waterfall steps", () => {
    const outcome: BusinessOutcomeDto = {
      id: "bo-1",
      title: "Created contact",
      status: "completed",
      sections: {
        timeline: [
          { index: 0, label: "TOOL hubspot.contact.create", status: "completed", summary: "Write" },
          { index: 1, label: "RESULT", status: "completed", summary: "Contact created" },
        ],
        verification: { verified: true, confidence: "verified", method: "read-after-write" },
      },
    }
    const stages = buildActivityTraceStages(outcome)
    expect(stages.map((s) => s.label)).toEqual(["TOOL", "RESULT", "VERIFICATION", "OUTCOME"])
    expect(stages.every((s) => s.summary || s.status)).toBe(true)
  })

  it("returns empty when no timeline, verification, or title", () => {
    expect(buildActivityTraceStages({ id: "empty" })).toEqual([])
  })

  it("does not invent INTENT/PLAN when only outcome title exists", () => {
    const stages = buildActivityTraceStages({
      id: "bo-2",
      title: "Something happened",
      status: "failed",
    })
    expect(stages).toHaveLength(1)
    expect(stages[0]?.label).toBe("OUTCOME")
    expect(stages[0]?.status).toBe("failed")
  })
})
