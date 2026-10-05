import { describe, expect, it } from "vitest"
import { summarizeActivityView } from "@/lib/activity-view-summary"

describe("Activity view summaries", () => {
  it("counts loaded statuses without treating successful execution as verification", () => {
    expect(summarizeActivityView([
      { status: "running" }, { status: "executing" },
      { status: "awaiting_approval" }, { sections: { approval: { status: "pending" } } },
      { status: "completed" }, { status: "succeeded" }, { status: "failed" },
    ])).toEqual({ running: 2, approval: 2, completed: 2, verified: 0 })
  })
  it("uses verification evidence and honors an explicit unverified result", () => {
    expect(summarizeActivityView([
      { sections: { verification: { verified: true } } },
      { lifecycleState: "verified" },
      { sections: { verification: { confidence: "verified" } } },
      { sections: { verification: { verified: false, confidence: "verified" } } },
    ]).verified).toBe(3)
  })
  it("does not inflate an empty filtered view", () => {
    expect(summarizeActivityView([])).toEqual({ running: 0, approval: 0, completed: 0, verified: 0 })
  })
})
