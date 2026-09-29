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
})
