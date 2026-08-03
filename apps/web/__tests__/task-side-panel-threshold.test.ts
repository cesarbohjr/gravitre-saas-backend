import { describe, expect, it } from "vitest"
import {
  SIDE_PANEL_STEP_THRESHOLD,
  shouldShowTaskSidePanel,
} from "@/lib/task-side-panel-threshold"

describe("shouldShowTaskSidePanel", () => {
  it("keeps single-step tasks inline-only", () => {
    expect(shouldShowTaskSidePanel(["Running: Search contacts"], null)).toBe(false)
    expect(
      shouldShowTaskSidePanel(null, {
        params: { steps: [{ label: "Create contact list" }] },
      }),
    ).toBe(false)
  })

  it("opens at the evidence-based threshold of 3", () => {
    expect(SIDE_PANEL_STEP_THRESHOLD).toBe(3)
    expect(
      shouldShowTaskSidePanel(
        [
          "Completed: Searching the web",
          "Completed: Checking connector status",
          "Running: Create contact list",
        ],
        null,
      ),
    ).toBe(true)
    expect(
      shouldShowTaskSidePanel(null, {
        params: {
          steps: [
            { label: "Create campaign" },
            { label: "Add ad group" },
            { label: "Add keywords" },
          ],
        },
      }),
    ).toBe(true)
  })
})
