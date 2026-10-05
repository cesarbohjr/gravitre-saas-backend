import { describe, expect, it } from "vitest"
import { readableAssignmentText } from "@/lib/assignments-list"

describe("readableAssignmentText", () => {
  it("keeps plain text unchanged", () => {
    expect(readableAssignmentText("  Enrich Q3 accounts ")).toBe("Enrich Q3 accounts")
  })

  it("picks the human field from a serialized payload", () => {
    expect(readableAssignmentText('{"id":"x","objective":"Draft the weekly digest"}')).toBe("Draft the weekly digest")
    expect(readableAssignmentText('[{"task":{"description":"Reconcile invoices"}}]')).toBe("Reconcile invoices")
  })

  it("strips markup when the payload has no readable field", () => {
    expect(readableAssignmentText('{"a": 1')).toBe("a : 1")
    expect(readableAssignmentText("{}")).toBe("Agent task")
  })

  it("reads the summary from a department handoff title", () => {
    expect(
      readableAssignmentText(
        'Sales handoff JSON:{"summary":"Objective is to find the best global shipping provider."}',
      ),
    ).toBe("Sales: Objective is to find the best global shipping provider.")
    expect(
      readableAssignmentText(
        'CS handoff JSON:{"summary":"Request to review customer complaints from the last month."}',
      ),
    ).toBe("CS: Request to review customer complaints from the last month.")
  })
})
