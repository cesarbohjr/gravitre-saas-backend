import { describe, expect, it } from "vitest"
import { computeMapFocusTransform } from "@/components/intelligence/map/map-spatial-focus"

describe("computeMapFocusTransform", () => {
  const vb = { w: 1000, h: 520 }
  const center = { cx: 500, cy: 260 }

  it("returns null when no highlights", () => {
    expect(computeMapFocusTransform([], new Map(), center, vb)).toBeNull()
  })

  it("zooms toward highlighted nodes including core", () => {
    const positions = new Map([
      ["dept:sales", { x: 700, y: 260 }],
      ["dept:support", { x: 300, y: 260 }],
    ])
    const transform = computeMapFocusTransform(["dept:sales"], positions, center, vb)
    expect(transform).not.toBeNull()
    expect(transform!.scale).toBeGreaterThan(1)
    expect(Math.abs(transform!.translateX)).toBeGreaterThan(0)
  })
})
