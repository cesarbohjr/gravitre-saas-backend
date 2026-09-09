import { describe, expect, it } from "vitest"
import {
  clampFloatSize,
  clampFloatTranslate,
  GRAVITRE_FLOAT_DEFAULT_SIZE,
  GRAVITRE_FLOAT_MIN_SIZE,
} from "@/lib/ai-float-geometry"
import { floatContentTiers } from "@/lib/float-content-tiers"

describe("ai-float-geometry", () => {
  it("clamps size into min/max against a small viewport", () => {
    const next = clampFloatSize(
      { width: 900, height: 900 },
      { width: 500, height: 500 },
    )
    expect(next.width).toBeLessThanOrEqual(500 - 24)
    expect(next.height).toBeLessThanOrEqual(500 - 24)
    expect(next.width).toBeGreaterThanOrEqual(GRAVITRE_FLOAT_MIN_SIZE.width)
  })

  it("keeps default size unchanged on a large viewport", () => {
    const next = clampFloatSize(GRAVITRE_FLOAT_DEFAULT_SIZE, { width: 1440, height: 900 })
    expect(next).toEqual(GRAVITRE_FLOAT_DEFAULT_SIZE)
  })

  it("clamps translate so a grab strip stays reachable", () => {
    const pos = clampFloatTranslate({ x: -9999, y: 9999 }, { width: 1280, height: 800 })
    expect(pos.x).toBe(-(1280 - 48))
    expect(pos.y).toBe(800 - 48)
  })
})

describe("floatContentTiers", () => {
  it("maps widths to small/medium/large", () => {
    expect(floatContentTiers(400)).toBe("small")
    expect(floatContentTiers(520)).toBe("medium")
    expect(floatContentTiers(700)).toBe("large")
  })
})
