/**
 * Creative Experience System — lightweight performance helpers.
 * Full FPS monitoring comes later; Pilot 1 uses visibility + reduced-motion + quality.
 */

import type { CreativeQuality } from "./tokens"

export type CreativePerformanceSnapshot = {
  quality: CreativeQuality
  reducedMotion: boolean
  visible: boolean
  documentHidden: boolean
  shouldAnimate: boolean
  dprCap: number
}

export function resolveCreativeQuality(input: {
  reducedMotion?: boolean
  preferLow?: boolean
  preferMedium?: boolean
  forceFallback?: boolean
}): CreativeQuality {
  if (input.forceFallback || input.reducedMotion) return "fallback"
  if (input.preferLow) return "low"
  if (input.preferMedium) return "medium"
  return "high"
}

export function creativeDprCap(quality: CreativeQuality): number {
  switch (quality) {
    case "high":
      return 2
    case "medium":
      return 1.5
    case "low":
    case "fallback":
      return 1
  }
}

export function shouldRunCreativeAnimation(input: {
  reducedMotion: boolean
  visible: boolean
  documentHidden?: boolean
}): boolean {
  if (input.reducedMotion) return false
  if (input.documentHidden) return false
  return input.visible
}

export function snapshotCreativePerformance(input: {
  reducedMotion: boolean
  visible: boolean
  documentHidden?: boolean
  preferLow?: boolean
  preferMedium?: boolean
}): CreativePerformanceSnapshot {
  const quality = resolveCreativeQuality({
    reducedMotion: input.reducedMotion,
    preferLow: input.preferLow,
    preferMedium: input.preferMedium,
  })
  const documentHidden = Boolean(input.documentHidden)
  return {
    quality,
    reducedMotion: input.reducedMotion,
    visible: input.visible,
    documentHidden,
    shouldAnimate: shouldRunCreativeAnimation({
      reducedMotion: input.reducedMotion,
      visible: input.visible,
      documentHidden,
    }),
    dprCap: creativeDprCap(quality),
  }
}
