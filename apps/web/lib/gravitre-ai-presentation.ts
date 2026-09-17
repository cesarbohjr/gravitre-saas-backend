/**
 * Canonical AI workspace presentation vocabulary with a compatibility layer
 * over the shipped names (helper / float / expanded / fullscreen).
 *
 * Phase 1A of UX Reset 1.0: map first, prove behavior, then retire aliases.
 * Do not big-bang rename call sites.
 *
 *   Canonical     Legacy
 *   minimized  -> helper   (launcher; floatWorkspaceOpen === false)
 *   compact    -> float    (floating ~500–600px window)
 *   expanded   -> expanded
 *   fullscreen -> fullscreen  (/ai is this presentation of the same runtime)
 */

export const CANONICAL_PRESENTATION_STATES = [
  "minimized",
  "compact",
  "expanded",
  "fullscreen",
] as const

export type CanonicalPresentationState = (typeof CANONICAL_PRESENTATION_STATES)[number]

/** Names still stored in React state and most components. */
export const LEGACY_PRESENTATION_MODES = ["helper", "float", "expanded", "fullscreen"] as const

export type LegacyPresentationMode = (typeof LEGACY_PRESENTATION_MODES)[number]

/** Anything a caller may pass into setPresentationMode / summon. */
export type GravitrePresentationInput = CanonicalPresentationState | LegacyPresentationMode

const CANONICAL_TO_LEGACY: Record<CanonicalPresentationState, LegacyPresentationMode> = {
  minimized: "helper",
  compact: "float",
  expanded: "expanded",
  fullscreen: "fullscreen",
}

const LEGACY_TO_CANONICAL: Record<LegacyPresentationMode, CanonicalPresentationState> = {
  helper: "minimized",
  float: "compact",
  expanded: "expanded",
  fullscreen: "fullscreen",
}

export function isLegacyPresentationMode(value: string): value is LegacyPresentationMode {
  return (LEGACY_PRESENTATION_MODES as readonly string[]).includes(value)
}

export function isCanonicalPresentationState(value: string): value is CanonicalPresentationState {
  return (CANONICAL_PRESENTATION_STATES as readonly string[]).includes(value)
}

/** Normalize any accepted name to the shipped React-state value. */
export function toLegacyPresentationMode(input: GravitrePresentationInput | null | undefined): LegacyPresentationMode {
  if (!input) return "float"
  if (isCanonicalPresentationState(input)) return CANONICAL_TO_LEGACY[input]
  if (isLegacyPresentationMode(input)) return input
  return "float"
}

export function toCanonicalPresentationState(
  input: GravitrePresentationInput | null | undefined,
): CanonicalPresentationState {
  if (!input) return "compact"
  if (isCanonicalPresentationState(input)) return input
  if (isLegacyPresentationMode(input)) return LEGACY_TO_CANONICAL[input]
  return "compact"
}

/**
 * Visible presentation: the launcher is minimized whenever the workspace
 * window is closed, regardless of the last remembered mode.
 */
export function deriveCanonicalPresentation(args: {
  floatWorkspaceOpen: boolean
  mode: GravitrePresentationInput
}): CanonicalPresentationState {
  if (!args.floatWorkspaceOpen) return "minimized"
  const canonical = toCanonicalPresentationState(args.mode)
  if (canonical === "minimized") return "compact"
  return canonical
}
