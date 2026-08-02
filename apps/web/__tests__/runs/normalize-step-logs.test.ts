import { describe, expect, it } from "vitest"
import { normalizeStepLogs } from "@/lib/runs/step-summary"

describe("normalizeStepLogs", () => {
  it("returns empty for nullish", () => {
    expect(normalizeStepLogs(null)).toEqual([])
    expect(normalizeStepLogs(undefined)).toEqual([])
  })

  it("passes through string arrays", () => {
    expect(normalizeStepLogs(["a", "b"])).toEqual(["a", "b"])
  })

  it("wraps a single JSON string (execution engine shape)", () => {
    const blob = JSON.stringify({ node_id: "n1", error_message: "boom" })
    expect(normalizeStepLogs(blob)).toEqual([blob])
  })

  it("stringifies a parsed object (jsonb object, not array)", () => {
    const obj = { node_id: "n1", duration_ms: 12 }
    expect(normalizeStepLogs(obj)).toEqual([JSON.stringify(obj)])
  })

  it("does not throw when callers .map the result", () => {
    const lines = normalizeStepLogs({ foo: 1 }).map((l) => l.toUpperCase())
    expect(lines[0]).toContain("FOO")
  })
})
