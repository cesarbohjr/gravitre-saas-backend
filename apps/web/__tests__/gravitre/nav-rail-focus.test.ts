import { describe, expect, it } from "vitest"
import { cycleNavFocus } from "@/lib/nav-rail-focus"

describe("Navigation B keyboard focus", () => {
  it("moves down and wraps", () => {
    expect(cycleNavFocus(0, 1, 3)).toBe(1)
    expect(cycleNavFocus(2, 1, 3)).toBe(0)
  })

  it("moves up and wraps", () => {
    expect(cycleNavFocus(0, -1, 3)).toBe(2)
  })

  it("starts from unfocused on arrow down", () => {
    expect(cycleNavFocus(-1, 1, 4)).toBe(0)
  })
})
