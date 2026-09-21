import { describe, expect, it } from "vitest"
import { resolveOverviewFieldState } from "@/lib/intelligence/overview-field-state"

describe("I1 overview field state", () => {
  it("shows sparse honesty on knows lens when rels exist but entities are zero", () => {
    const state = resolveOverviewFieldState({
      snapshotLoadState: "READY",
      activeLens: "knows",
      knownEntities: 0,
      knownRels: 12,
      graphNodes: 3,
    })
    expect(state.isSparse).toBe(true)
    expect(state.showMap).toBe(false)
  })

  it("does not treat sparse rels as empty on predicts lens", () => {
    const state = resolveOverviewFieldState({
      snapshotLoadState: "READY",
      activeLens: "predicts",
      knownEntities: 0,
      knownRels: 12,
      graphNodes: 3,
    })
    expect(state.isSparse).toBe(false)
    expect(state.showMap).toBe(true)
  })

  it("empty when no entities, rels, or graph nodes", () => {
    const state = resolveOverviewFieldState({
      snapshotLoadState: "READY",
      activeLens: "knows",
      knownEntities: 0,
      knownRels: 0,
      graphNodes: 1,
    })
    expect(state.isEmpty).toBe(true)
    expect(state.showMap).toBe(false)
  })
})
