// @vitest-environment jsdom

/**
 * Proves the measured diameter reaches the DOM.
 *
 * The pure sizing tests in __tests__/lib/voice-orb-sizing.test.ts cover the maths.
 * What they cannot show is that GravitreOrb stops using the fixed Tailwind pairs
 * once a measurement exists -- which is the actual defect, since those pairs
 * stepped on the `sm:` *viewport* breakpoint and so ignored the container.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { act } from "react"
import { GravitreOrb } from "@/components/gravitre/assistant/voice-presentation"
import { orbBloomPx, voiceOrbSize } from "@/lib/voice-orb-sizing"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) act(() => root!.unmount())
  root = null
  container.remove()
})

function render(props: Record<string, unknown>) {
  root = createRoot(container)
  act(() => {
    root!.render(createElement(GravitreOrb, { speaker: "agent", ...props } as never))
  })
  return container.querySelector("[data-gravitre-orb]") as HTMLElement
}

describe("GravitreOrb sizing source", () => {
  it("uses the measured diameter and drops the fixed viewport classes", () => {
    const el = render({ diameter: 96 })
    expect(el.getAttribute("data-voice-orb-sizing")).toBe("container")
    expect(el.style.height).toBe("96px")
    expect(el.style.width).toBe("96px")
    // The old pairs stepped on a viewport media query, so they must be gone.
    expect(el.className).not.toContain("h-[104px]")
    expect(el.className).not.toContain("sm:h-[128px]")
    expect(el.className).not.toContain("h-[220px]")
    expect(el.className).not.toContain("sm:h-[280px]")
  })

  it("scales the bloom with the diameter", () => {
    const small = render({ diameter: 96 })
    expect(small.style.getPropertyValue("--gv-orb-bloom")).toBe(`${orbBloomPx(96)}px`)
    act(() => root!.unmount())
    root = null

    const big = render({ diameter: 280 })
    const smallBloom = orbBloomPx(96)
    const bigBloom = orbBloomPx(280)
    expect(big.style.getPropertyValue("--gv-orb-bloom")).toBe(`${bigBloom}px`)
    expect(bigBloom).toBeGreaterThan(smallBloom)
  })

  it("falls back to the class pairs when there is nothing measured yet", () => {
    // First paint: the host element does not exist until an effect runs, so the
    // orb must still render at a sensible size rather than 0.
    for (const diameter of [null, undefined, 0]) {
      const el = render({ diameter, compact: true })
      expect(el.getAttribute("data-voice-orb-sizing")).toBe("class")
      expect(el.className).toContain("h-[104px]")
      expect(el.style.height).toBe("")
      act(() => root!.unmount())
      root = null
    }
  })

  it("keeps a caller's className override winning, which the 36px launcher relies on", () => {
    const el = render({ className: "!h-9 !w-9" })
    expect(el.className).toContain("!h-9")
  })
})

describe("end to end: container size decides the rendered diameter", () => {
  it("renders a smaller orb in a narrow container than a wide one", () => {
    // The regression this guards: identical viewport, different containers. The
    // old code produced the same 128px orb for both.
    const narrow = voiceOrbSize({ containerWidth: 400, containerHeight: 600 })
    const wide = voiceOrbSize({ containerWidth: 1200, containerHeight: 600 })

    const a = render({ diameter: narrow.diameter })
    const narrowPx = Number.parseInt(a.style.height, 10)
    act(() => root!.unmount())
    root = null

    const b = render({ diameter: wide.diameter })
    const widePx = Number.parseInt(b.style.height, 10)

    expect(narrowPx).toBeLessThan(widePx)
    expect(narrowPx).toBeLessThan(400)
  })
})
