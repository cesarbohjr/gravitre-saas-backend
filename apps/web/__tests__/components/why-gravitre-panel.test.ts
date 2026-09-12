import { describe, expect, it } from "vitest"
import {
  collectDepartmentGaps,
  evidenceEventCount,
  flattenPriorities,
  relativeFreshness,
  sourceStatusLabel,
  type AllDepartmentsPayload,
} from "@/components/intelligence/why-gravitre-panel"

/**
 * Phase 4 (2026-09-11) — "Why Gravitre thinks this."
 *
 * These exercise the exact data-shaping/arithmetic that would render into
 * the evidence graph. This is the same class of bug (silent scaling/mapping
 * error) that shipped as the Improves-pillar 100x bug in brief-Phase 3 and
 * was only caught by live browser verification -- these tests exist so the
 * next regression is caught by `vitest run`, not just a live pass.
 */

describe("why-gravitre-panel — sourceStatusLabel", () => {
  it("maps every real backend SourceStatus to an honest label", () => {
    expect(sourceStatusLabel("live_connector")).toBe("Connected source")
    expect(sourceStatusLabel("knowledge_fabric_only")).toBe("Knowledge only, not connected")
    expect(sourceStatusLabel("missing")).toBe("No source available")
    expect(sourceStatusLabel(undefined)).toBe("Unknown source state")
  })
})

describe("why-gravitre-panel — evidenceEventCount", () => {
  it("sums real eventHits + externalSignalHits, never fabricates a count", () => {
    expect(evidenceEventCount({ eventHits: 6, externalSignalHits: 1 })).toBe(7)
    expect(evidenceEventCount({ eventHits: 0, externalSignalHits: 3 })).toBe(3)
    expect(evidenceEventCount({})).toBe(0)
    expect(evidenceEventCount({ status: "missing" })).toBe(0)
  })
})

describe("why-gravitre-panel — relativeFreshness", () => {
  const now = Date.parse("2026-09-11T20:00:00.000Z")

  it("formats real capturedAt deltas honestly, never a fabricated timestamp", () => {
    expect(relativeFreshness("2026-09-11T20:00:00.000Z", now)).toBe("Evidence captured just now")
    expect(relativeFreshness("2026-09-11T19:55:00.000Z", now)).toBe("Evidence captured 5m ago")
    expect(relativeFreshness("2026-09-11T18:00:00.000Z", now)).toBe("Evidence captured 2h ago")
    expect(relativeFreshness("2026-09-09T20:00:00.000Z", now)).toBe("Evidence captured 2d ago")
  })

  it("discloses a gap instead of inventing a timestamp when capturedAt is missing/invalid", () => {
    expect(relativeFreshness(undefined, now)).toBe("Freshness not available")
    expect(relativeFreshness("not-a-date", now)).toBe("Freshness not available")
  })
})

describe("why-gravitre-panel — flattenPriorities", () => {
  const payload: AllDepartmentsPayload = {
    capturedAt: "2026-09-11T20:00:00.000Z",
    departments: [
      {
        department: "sales",
        priorities: [
          { workObjectId: "s1", title: "Sales priority A", priorityScore: 40 },
          { workObjectId: "s2", title: "Sales priority B", priorityScore: 90 },
        ],
      },
      {
        department: "finance",
        priorities: [{ workObjectId: "f1", title: "Finance priority A", priorityScore: 78 }],
      },
      {
        department: "hr",
        priorities: [],
      },
    ],
  }

  it("flattens across departments and sorts by real priorityScore descending", () => {
    const flattened = flattenPriorities(payload, 10)
    expect(flattened.map((row) => row.workObjectId)).toEqual(["s2", "f1", "s1"])
  })

  it("caps at maxItems without dropping the highest-scored items", () => {
    const flattened = flattenPriorities(payload, 2)
    expect(flattened.map((row) => row.workObjectId)).toEqual(["s2", "f1"])
  })

  it("fills in the parent department when an item omits its own department field", () => {
    const flattened = flattenPriorities(payload, 10)
    const salesItem = flattened.find((row) => row.workObjectId === "s2")
    expect(salesItem?.department).toBe("sales")
  })

  it("returns an empty array honestly when there is no scored data yet", () => {
    expect(flattenPriorities(undefined)).toEqual([])
    expect(flattenPriorities({ departments: [] })).toEqual([])
  })
})

describe("why-gravitre-panel — collectDepartmentGaps", () => {
  it("surfaces real backend-disclosed gaps rather than a generic message", () => {
    const payload: AllDepartmentsPayload = {
      departments: [
        { department: "sales", gaps: ["No sales WorkObjects with current activity were found."] },
        { department: "marketing", gaps: ["Campaign engagement: missing source(s) Google Ads."] },
      ],
    }
    expect(collectDepartmentGaps(payload)).toEqual([
      "No sales WorkObjects with current activity were found.",
      "Campaign engagement: missing source(s) Google Ads.",
    ])
  })

  it("caps at maxGaps and returns empty honestly when nothing is disclosed", () => {
    const payload: AllDepartmentsPayload = {
      departments: [{ gaps: ["a", "b", "c"] }],
    }
    expect(collectDepartmentGaps(payload, 2)).toEqual(["a", "b"])
    expect(collectDepartmentGaps(undefined)).toEqual([])
  })
})
