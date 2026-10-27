import { describe, expect, it } from "vitest"
import { createOverlapDuckState } from "./voice-overlap-duck"

describe("overlap duck lifecycle", () => {
  it("ducks and restores the same reply", () => {
    const state = createOverlapDuckState()
    expect(state.duck(10)).toBe(true)
    expect(state.isDucked()).toBe(true)
    expect(state.unduck(10)).toBe(true)
    expect(state.isDucked()).toBe(false)
  })

  it("ignores a delayed unduck from an older reply", () => {
    const state = createOverlapDuckState()
    expect(state.duck(10)).toBe(true)
    expect(state.duck(11)).toBe(false)
    expect(state.unduck(10)).toBe(false)
    expect(state.isDucked()).toBe(true)
    expect(state.unduck(11)).toBe(true)
  })

  it("rejects stale duck events after newer audio", () => {
    const state = createOverlapDuckState()
    expect(state.audio(12)).toBe(false)
    expect(state.duck(11)).toBe(false)
    expect(state.duck(12)).toBe(true)
  })

  it("newer reply audio releases an older duck", () => {
    const state = createOverlapDuckState()
    expect(state.duck(7)).toBe(true)
    expect(state.audio(8)).toBe(true)
    expect(state.isDucked()).toBe(false)
  })

  it("flush resets duck state", () => {
    const state = createOverlapDuckState()
    state.duck(3)
    expect(state.reset()).toBe(true)
    expect(state.isDucked()).toBe(false)
  })
})
