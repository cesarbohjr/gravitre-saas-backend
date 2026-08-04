import { describe, expect, it } from "vitest"
import {
  deriveNamedProgressSteps,
  formatStepCounter,
  isActionProgressStep,
} from "@/lib/chat-progress-steps"

describe("deriveNamedProgressSteps", () => {
  it("strips SSE status prefixes so labels stay human", () => {
    const steps = deriveNamedProgressSteps(
      [
        "Completed: Search contacts",
        "Running: Create contact list",
        "Step 3/3: Add contacts to list",
      ],
      null,
    )
    expect(steps).toEqual([
      { label: "Search contacts", status: "done" },
      { label: "Create contact list", status: "current" },
      { label: "Add contacts to list", status: "pending" },
    ])
    // The raw prefixes must never survive into a rendered label.
    for (const step of steps) {
      expect(step.label).not.toMatch(/^(Running:|Completed:|Step \d+\/\d+:)/i)
    }
  })

  it("drops internal routing chatter instead of showing it as a step", () => {
    const steps = deriveNamedProgressSteps(
      ["Running: Routing tier: research", "Completed: Search contacts"],
      null,
    )
    expect(steps).toEqual([{ label: "Search contacts", status: "done" }])
  })

  it("falls back to planned steps and marks the current index", () => {
    const steps = deriveNamedProgressSteps(null, {
      params: {
        steps: [{ label: "Create campaign" }, { label: "Add ad group" }, { label: "Add keywords" }],
        current_step_index: 1,
      },
    })
    expect(steps.map((s) => s.status)).toEqual(["done", "current", "pending"])
    expect(steps[1].label).toBe("Add ad group")
  })

  it("prefers live progress over planned steps", () => {
    const steps = deriveNamedProgressSteps(["Running: Live step"], {
      params: { steps: [{ label: "Planned step" }] },
    })
    expect(steps).toEqual([{ label: "Live step", status: "current" }])
  })

  it("returns an empty list when there is nothing to show", () => {
    expect(deriveNamedProgressSteps(null, null)).toEqual([])
    expect(deriveNamedProgressSteps([" ", ""], null)).toEqual([])
  })
})

describe("formatStepCounter", () => {
  it("reports position while a step is running", () => {
    expect(
      formatStepCounter([
        { label: "a", status: "done" },
        { label: "b", status: "current" },
        { label: "c", status: "pending" },
      ]),
    ).toBe("Step 2 of 3")
  })

  it("reports completion when every step is done", () => {
    expect(
      formatStepCounter([
        { label: "a", status: "done" },
        { label: "b", status: "done" },
      ]),
    ).toBe("2 of 2 complete")
  })

  it("returns null when there are no steps", () => {
    expect(formatStepCounter([])).toBeNull()
  })
})

describe("isActionProgressStep", () => {
  it("recognises only the status-prefixed SSE strings", () => {
    expect(isActionProgressStep("Running: x")).toBe(true)
    expect(isActionProgressStep("Completed: x")).toBe(true)
    expect(isActionProgressStep("Step 1/4: x")).toBe(true)
    expect(isActionProgressStep("Thinking about it")).toBe(false)
  })
})
