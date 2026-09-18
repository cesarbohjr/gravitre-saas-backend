import { describe, expect, it } from "vitest"
import {
  collectRunActions,
  collectRunSystems,
  lastCompletedStepSummary,
  runOutcomeHeadline,
} from "@/lib/runs/run-outcome-display"

describe("run-outcome-display", () => {
  it("prefers a recorded business title and never invents a result", () => {
    expect(
      runOutcomeHeadline({
        businessTitle: "Contact assigned",
        goal: "Route inbound",
        lastCompletedSummary: "wrote owner",
      }),
    ).toBe("Contact assigned")
    expect(runOutcomeHeadline({})).toBeNull()
  })

  it("collects systems and actions only from recorded snapshots", () => {
    const steps = [
      {
        name: "CRM write",
        status: "completed",
        outputSnapshot: { invoke_action: "hubspot.contacts.update", summary: "owner set" },
      },
      { name: "Notify", status: "pending", outputSnapshot: {} },
    ]
    expect(collectRunSystems(steps)).toEqual(["hubspot"])
    expect(collectRunActions(steps)).toEqual(["hubspot.contacts.update", "Notify"])
    expect(lastCompletedStepSummary(steps)).toBe("owner set")
  })
})
