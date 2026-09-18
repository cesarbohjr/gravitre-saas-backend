import { describe, expect, it } from "vitest"
import { hasWorkArtifact, shouldRevealInspector } from "@/lib/gravitre-command-os"

describe("shouldRevealInspector", () => {
  it("stays closed with no selection and short tasks", () => {
    expect(shouldRevealInspector({ progressSteps: ["Running: Search"], pendingTask: null })).toBe(false)
  })

  it("opens when an inspect selection exists", () => {
    expect(shouldRevealInspector({ inspectSelection: { id: "hubspot" } })).toBe(true)
  })

  it("opens at the multi-step task threshold", () => {
    expect(
      shouldRevealInspector({
        progressSteps: [
          "Completed: Searching the web",
          "Completed: Checking connector status",
          "Running: Create contact list",
        ],
      }),
    ).toBe(true)
  })
})

describe("hasWorkArtifact", () => {
  it("is false for empty conversation state", () => {
    expect(hasWorkArtifact({})).toBe(false)
  })

  it("is true for an execution outcome", () => {
    expect(hasWorkArtifact({ executionResult: { title: "Lead routed", success: true } })).toBe(true)
  })

  it("is true for pending work or hosted files", () => {
    expect(hasWorkArtifact({ pendingTask: { title: "Write CRM" } })).toBe(true)
    expect(hasWorkArtifact({ hostedFiles: [{ id: "f1" }] })).toBe(true)
  })
})
