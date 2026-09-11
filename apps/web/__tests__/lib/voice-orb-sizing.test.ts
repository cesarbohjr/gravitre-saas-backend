import { describe, expect, it } from "vitest"
import {
  VOICE_ORB_BANDS,
  VOICE_ORB_CHROME_RESERVE,
  VOICE_ORB_MIN_DIAMETER,
  bandForWidth,
  orbBloomPx,
  voiceOrbSize,
} from "@/lib/voice-orb-sizing"
import { GRAVITRE_FLOAT_MIN_SIZE, GRAVITRE_FLOAT_MAX_SIZE } from "@/lib/ai-float-geometry"

/** Header chrome the float window puts above the orb host. */
const FLOAT_HEADER = 44

describe("the size follows the container, not the viewport", () => {
  it("gives a narrow container a small orb regardless of how wide the screen is", () => {
    // The actual bug: the step between orb sizes was the `sm:` *viewport* media
    // query, so a 400px float window on a wide monitor got the large orb. This
    // function never sees the viewport, which is the fix.
    const narrow = voiceOrbSize({ containerWidth: 400, containerHeight: 600 })
    const wide = voiceOrbSize({ containerWidth: 1200, containerHeight: 600 })
    expect(narrow.diameter).toBeLessThan(wide.diameter!)
    expect(narrow.band).toBe("compact")
    expect(wide.band).toBe("large")
  })

  it("grows continuously rather than jumping at a breakpoint", () => {
    const widths = [430, 470, 510, 550]
    const diameters = widths.map((w) => voiceOrbSize({ containerWidth: w, containerHeight: 900 }).diameter!)
    for (let i = 1; i < diameters.length; i += 1) {
      expect(diameters[i]).toBeGreaterThan(diameters[i - 1])
    }
  })

  it("never shrinks when the container grows, at any size", () => {
    let previous = 0
    for (let w = 320; w <= 1600; w += 8) {
      const { diameter } = voiceOrbSize({ containerWidth: w, containerHeight: 1200 })
      const value = diameter ?? 0
      expect(value).toBeGreaterThanOrEqual(previous)
      previous = value
    }
  })
})

describe("band ranges", () => {
  it("keeps each band inside its specified range", () => {
    const cases: Array<[number, string, number, number]> = [
      [400, "compact", 64, 96],
      [520, "windowed", 90, 130],
      [800, "expanded", 130, 180],
      [1400, "large", 160, 220],
    ]
    for (const [width, band, min, max] of cases) {
      const size = voiceOrbSize({ containerWidth: width, containerHeight: 1200 })
      expect(size.band).toBe(band)
      expect(size.diameter).toBeGreaterThanOrEqual(min)
      expect(size.diameter).toBeLessThanOrEqual(max)
    }
  })

  it("selects bands by width boundary", () => {
    expect(bandForWidth(419).name).toBe("compact")
    expect(bandForWidth(420).name).toBe("windowed")
    expect(bandForWidth(559).name).toBe("windowed")
    expect(bandForWidth(560).name).toBe("expanded")
    expect(bandForWidth(899).name).toBe("expanded")
    expect(bandForWidth(900).name).toBe("large")
  })

  it("falls back to a real band for a width it cannot measure yet", () => {
    // First paint reports 0 before the ResizeObserver fires.
    for (const width of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(VOICE_ORB_BANDS.map((b) => b.name)).toContain(bandForWidth(width).name)
    }
  })
})

describe("the orb never overflows its container", () => {
  // Sweeps the whole float window range plus short containers, because an orb
  // that fits the width and not the height is exactly how it overflowed before.
  it.each(["contained", "fullscreen"] as const)("%s: painted extent fits the height", (variant) => {
    for (let w = 320; w <= 1600; w += 16) {
      for (let h = 200; h <= 1200; h += 16) {
        const size = voiceOrbSize({ containerWidth: w, containerHeight: h, variant, amplitude: 1 })
        if (size.diameter == null) continue
        const available = h - VOICE_ORB_CHROME_RESERVE[variant]
        expect(
          size.painted,
          `orb painted ${size.painted}px into ${available}px at ${w}x${h} (${variant})`,
        ).toBeLessThanOrEqual(available)
      }
    }
  })

  it("fits the smallest float window the user can drag to", () => {
    const size = voiceOrbSize({
      containerWidth: GRAVITRE_FLOAT_MIN_SIZE.width,
      containerHeight: GRAVITRE_FLOAT_MIN_SIZE.height - FLOAT_HEADER,
      amplitude: 1,
    })
    expect(size.diameter).not.toBeNull()
    expect(size.diameter!).toBeLessThan(GRAVITRE_FLOAT_MIN_SIZE.width)
    expect(size.painted).toBeLessThanOrEqual(
      GRAVITRE_FLOAT_MIN_SIZE.height - FLOAT_HEADER - VOICE_ORB_CHROME_RESERVE.contained,
    )
  })

  it("still fits the largest float window", () => {
    const size = voiceOrbSize({
      containerWidth: GRAVITRE_FLOAT_MAX_SIZE.width,
      containerHeight: GRAVITRE_FLOAT_MAX_SIZE.height - FLOAT_HEADER,
      amplitude: 1,
    })
    expect(size.diameter).not.toBeNull()
    expect(size.painted).toBeLessThanOrEqual(
      GRAVITRE_FLOAT_MAX_SIZE.height - FLOAT_HEADER - VOICE_ORB_CHROME_RESERVE.contained,
    )
  })

  it("scales the bloom with the orb instead of a fixed spread", () => {
    // A fixed 78px bloom is unremarkable around a 280px orb and overflows a
    // small container around a 96px one.
    expect(orbBloomPx(280)).toBeGreaterThan(orbBloomPx(96))
    expect(orbBloomPx(96)).toBeLessThan(96)
  })
})

describe("containers too small for a full orb", () => {
  it("reports no orb rather than an illegible one", () => {
    // The minimized state has no full orb by design; the caller shows the
    // compact waveform instead.
    const size = voiceOrbSize({ containerWidth: 360, containerHeight: 180 })
    expect(size.diameter).toBeNull()
  })

  it("never returns a diameter below the legible minimum", () => {
    for (let h = 0; h <= 400; h += 4) {
      const { diameter } = voiceOrbSize({ containerWidth: 400, containerHeight: h })
      if (diameter != null) expect(diameter).toBeGreaterThanOrEqual(VOICE_ORB_MIN_DIAMETER)
    }
  })

  it("treats a zero-sized container as having no orb", () => {
    expect(voiceOrbSize({ containerWidth: 0, containerHeight: 0 }).diameter).toBeNull()
  })
})

describe("amplitude", () => {
  it("counts the amplitude scale in the painted extent", () => {
    const quiet = voiceOrbSize({ containerWidth: 800, containerHeight: 900, amplitude: 0 })
    const loud = voiceOrbSize({ containerWidth: 800, containerHeight: 900, amplitude: 1 })
    expect(loud.painted).toBeGreaterThan(quiet.painted)
    // The circle itself does not change size; only the transform does.
    expect(loud.diameter).toBe(quiet.diameter)
  })

  it("clamps out-of-range amplitude instead of trusting it", () => {
    const over = voiceOrbSize({ containerWidth: 800, containerHeight: 900, amplitude: 9 })
    const one = voiceOrbSize({ containerWidth: 800, containerHeight: 900, amplitude: 1 })
    expect(over.painted).toBe(one.painted)
    const under = voiceOrbSize({ containerWidth: 800, containerHeight: 900, amplitude: -5 })
    expect(under.painted).toBeLessThanOrEqual(one.painted)
  })
})
