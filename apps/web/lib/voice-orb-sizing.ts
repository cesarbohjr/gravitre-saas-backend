/**
 * How big the voice orb should be, decided by the container it actually sits in.
 *
 * The bug this replaces: the orb's size was two fixed Tailwind pairs
 * (104/128px when `compact`, 220/280px otherwise) and the step between them was
 * the `sm:` breakpoint -- a *viewport* media query. So a 400px-wide float window
 * on a wide desktop monitor got the 128px orb, because the viewport was wide even
 * though the container was not. Nothing in the voice path measured a container at
 * all: no ResizeObserver, no container queries.
 *
 * Two things constrain the diameter, and both matter:
 *
 *   - width, which sets the band, and
 *   - available height, because the orb shares its container with a label, a
 *     subtitle and a control bar. A diameter that fits the width and not the
 *     height is how an orb overflows a short container.
 *
 * The returned value is a plain number of px. Callers apply it as an inline
 * style rather than a class, because the whole point is that it is continuous
 * rather than snapped to a breakpoint.
 */

export type VoiceOrbBandName = "compact" | "windowed" | "expanded" | "large"

export type VoiceOrbBand = {
  name: VoiceOrbBandName
  /** Upper bound of container width, exclusive of the next band. */
  maxWidth: number
  min: number
  max: number
}

/**
 * Bands come from the sizes this work was specified against: FULLSCREEN/LARGE
 * 160-220, EXPANDED 130-180, WINDOWED 90-130, COMPACT 64-96. They overlap on
 * purpose -- the ranges are what the diameter is clamped into, not disjoint
 * buckets, so growing a window moves the orb continuously instead of jumping.
 */
export const VOICE_ORB_BANDS: readonly VoiceOrbBand[] = [
  { name: "compact", maxWidth: 420, min: 64, max: 96 },
  { name: "windowed", maxWidth: 560, min: 90, max: 130 },
  { name: "expanded", maxWidth: 900, min: 130, max: 180 },
  { name: "large", maxWidth: Number.POSITIVE_INFINITY, min: 160, max: 220 },
]

/**
 * Share of container width the orb targets before clamping.
 *
 * Chosen so the target lands *inside* each band across that band's width range
 * rather than pinning to its maximum. A larger ratio (0.42 was tried) saturates
 * every band immediately, which silently reproduces the fixed-size behaviour this
 * module exists to remove -- the continuous-growth test catches exactly that.
 */
const WIDTH_RATIO = 0.22

/**
 * Vertical space the surrounding chrome needs. Fullscreen uses larger type
 * (text-4xl), a bigger control bar (h-14) and more generous margins, so it
 * reserves more.
 */
export const VOICE_ORB_CHROME_RESERVE = { contained: 150, fullscreen: 200 } as const

/**
 * Below this there is not enough room for a legible orb plus its chrome. The
 * caller should show the compact waveform instead -- the minimized state has no
 * full orb by design.
 */
export const VOICE_ORB_MIN_DIAMETER = 56

/**
 * The CSS pulse draws a bloom outside the circle. It used to be a fixed spread
 * (up to 78px), which is fine around a 280px orb and overflows a small container
 * around a 96px one. Expressed as a fraction of the diameter it scales with the
 * orb instead.
 */
const BLOOM_RATIO = 0.28

export function bandForWidth(width: number): VoiceOrbBand {
  // Non-finite or absurd widths happen during first paint, before measurement.
  const w = Number.isFinite(width) && width > 0 ? width : 0
  return VOICE_ORB_BANDS.find((band) => w < band.maxWidth) ?? VOICE_ORB_BANDS[VOICE_ORB_BANDS.length - 1]
}

/** Bloom spread in px for a given diameter, so it never exceeds its container. */
export function orbBloomPx(diameter: number): number {
  return Math.round(diameter * BLOOM_RATIO)
}

export type VoiceOrbSizeInput = {
  containerWidth: number
  containerHeight: number
  variant?: "contained" | "fullscreen"
  /** Peak 0-1. The orb scales up slightly with amplitude, which must still fit. */
  amplitude?: number | null
}

export type VoiceOrbSize = {
  /** px, or null when the container is too small for a full orb. */
  diameter: number | null
  band: VoiceOrbBandName
  bloom: number
  /** Largest painted extent including bloom and amplitude scale. */
  painted: number
}

/** Maximum extra scale the amplitude transform applies (matches GravitreOrb). */
const MAX_AMPLITUDE_SCALE = 1.1

export function voiceOrbSize({
  containerWidth,
  containerHeight,
  variant = "contained",
  amplitude,
}: VoiceOrbSizeInput): VoiceOrbSize {
  const band = bandForWidth(containerWidth)
  const none = { diameter: null, band: band.name, bloom: 0, painted: 0 } as const

  // Height decides first, because it is the constraint that can rule the orb out
  // entirely. Once the chrome has taken its share there may be nothing left, and
  // clamping a width-derived value up to the band minimum would otherwise invent
  // an orb for a container with no room for one -- including an unmeasured 0x0
  // container on first paint.
  const available = containerHeight - VOICE_ORB_CHROME_RESERVE[variant]
  if (!Number.isFinite(available) || available <= 0) return none

  // The bloom and the amplitude scale both paint outside the circle, so the
  // circle has to be small enough that the whole painted extent still fits.
  const ceiling = Math.floor(available / (MAX_AMPLITUDE_SCALE + BLOOM_RATIO))

  // Width sets the target; the band's range is the clamp.
  const fromWidth = Math.round(containerWidth * WIDTH_RATIO)
  const diameter = Math.min(Math.min(Math.max(fromWidth, band.min), band.max), ceiling)

  if (!Number.isFinite(diameter) || diameter < VOICE_ORB_MIN_DIAMETER) return none

  const bloom = orbBloomPx(diameter)
  const scale = amplitude != null ? 1 + Math.min(Math.max(amplitude, 0), 1) * 0.1 : 1
  return {
    diameter,
    band: band.name,
    bloom,
    painted: Math.round(diameter * scale + bloom),
  }
}
