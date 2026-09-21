import { describe, expect, it } from "vitest"
import { buildChangeEvents } from "@/lib/intelligence/build-change-events"

describe("I2 buildChangeEvents", () => {
  it("derives events from snapshot learnings and predictions only", () => {
    const events = buildChangeEvents({
      snapshot: {
        learnings: [{ id: "l1", businessStatement: "Revenue trend up", learnedAt: "2026-09-01" }],
        predictions: [{ id: "p1", businessStatement: "Churn risk" }],
        outcomes: [],
      },
    } as Parameters<typeof buildChangeEvents>[0])

    expect(events).toHaveLength(2)
    expect(events[0]?.kind).toBe("learned")
    expect(events[1]?.kind).toBe("prediction")
    expect(events[0]?.focusNodeIds).toEqual(["learning:l1"])
  })

  it("maps outcome entity ids to kg node focus ids", () => {
    const events = buildChangeEvents({
      snapshot: {
        learnings: [],
        predictions: [],
        outcomes: [
          {
            id: "o1",
            event: "contact_created",
            entityId: "42",
            entityType: "contact",
            createdAt: "2026-09-02",
          },
        ],
      },
    } as Parameters<typeof buildChangeEvents>[0])

    expect(events[0]?.kind).toBe("changed")
    expect(events[0]?.focusNodeIds).toEqual(["kg:contact:42"])
  })

  it("returns empty when snapshot missing", () => {
    expect(buildChangeEvents(null)).toEqual([])
    expect(buildChangeEvents({} as Parameters<typeof buildChangeEvents>[0])).toEqual([])
  })
})
