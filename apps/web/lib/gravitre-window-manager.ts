/**
 * Gravitre Window Manager — presentation policy (Slice 0 / 3.0 Plus).
 *
 * Owns: mode vocabulary, contextual defaults, remembered preference, identity
 * contract for chrome. Does **not** own conversation / task / voice / approval
 * / execution state — those remain with the Intelligence Core + provider
 * snapshots.
 *
 * G-STRUCT A3 (2026-09-24): Option A — contextual default + remembered preference.
 * Docked is not the universal default.
 */

import {
  toCanonicalPresentationState,
  type CanonicalPresentationState,
  type GravitrePresentationInput,
  type LegacyPresentationMode,
} from "@/lib/gravitre-ai-presentation"

/** Spec §15 / GRAVITRE_WINDOW_STATES — all seven modes. */
export const WINDOW_MANAGER_MODES = [
  "compact",
  "floating",
  "docked",
  "expanded",
  "fullscreen",
  "minimized",
  "restored",
] as const

export type WindowManagerMode = (typeof WINDOW_MANAGER_MODES)[number]

/** Modes that can be persisted as a user preference (not restored/minimized). */
export const WINDOW_MANAGER_PREFERENCE_MODES = [
  "compact",
  "floating",
  "docked",
  "expanded",
  "fullscreen",
] as const

export type WindowManagerPreferenceMode = (typeof WINDOW_MANAGER_PREFERENCE_MODES)[number]

export const GRAVITRE_WM_PREFERENCE_STORAGE_KEY = "gravitre.wm.preferred-mode.v1"

/** Identities chrome must carry across mode transitions — not owned by WM. */
export interface WindowManagerIdentity {
  conversationId: string | null
  taskId: string | null
  artifactId: string | null
  approvalId: string | null
  voiceSessionId: string | null
}

export interface WindowManagerContextHints {
  pathname: string
  viewportWidth: number
  hasActiveArtifact?: boolean
  hasPendingApproval?: boolean
  voiceActive?: boolean
  expertWorkspace?: boolean
}

export function isWindowManagerMode(value: string): value is WindowManagerMode {
  return (WINDOW_MANAGER_MODES as readonly string[]).includes(value)
}

export function isWindowManagerPreferenceMode(value: string): value is WindowManagerPreferenceMode {
  return (WINDOW_MANAGER_PREFERENCE_MODES as readonly string[]).includes(value)
}

/**
 * Map Window Manager modes onto the shipped presentation / React-state layer.
 * `restored` is an action, not a stored mode.
 */
export function windowManagerModeToPresentation(
  mode: WindowManagerMode,
): Exclude<WindowManagerMode, "restored"> | CanonicalPresentationState {
  switch (mode) {
    case "restored":
      return "compact"
    case "floating":
      return "floating"
    case "docked":
      return "docked"
    case "compact":
      return "compact"
    case "expanded":
      return "expanded"
    case "fullscreen":
      return "fullscreen"
    case "minimized":
      return "minimized"
  }
}

/** Prefer WM vocabulary when reading presentation state. */
export function presentationToWindowManagerMode(
  input: GravitrePresentationInput | null | undefined,
): Exclude<WindowManagerMode, "restored"> {
  const canonical = toCanonicalPresentationState(input)
  if (canonical === "floating" || canonical === "docked") return canonical
  return canonical
}

/**
 * Contextual default (G-STRUCT Option A) — preference overrides this when set.
 * Never forces docked as the universal default.
 */
export function resolveContextualWindowDefault(hints: WindowManagerContextHints): WindowManagerPreferenceMode {
  const path = hints.pathname.split("?")[0] ?? ""
  const narrow = hints.viewportWidth > 0 && hints.viewportWidth < 768
  const expert =
    hints.expertWorkspace === true ||
    /\/workflows\/[^/]+\/builder/.test(path) ||
    path.startsWith("/intelligence") ||
    path.startsWith("/model-studio") ||
    path.includes("/connectors/")

  if (narrow) return "compact"
  if (hints.voiceActive) return "expanded"
  if (hints.hasPendingApproval) return "floating"
  if (hints.hasActiveArtifact && !expert) return "expanded"
  if (expert) return "docked"
  if (path === "/ai" || path.startsWith("/ai/")) return "expanded"
  return "floating"
}

export function readWindowManagerPreference(
  storage: Pick<Storage, "getItem"> | null | undefined = typeof window !== "undefined" ? window.localStorage : null,
): WindowManagerPreferenceMode | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY)
    if (!raw || !isWindowManagerPreferenceMode(raw)) return null
    return raw
  } catch {
    return null
  }
}

export function writeWindowManagerPreference(
  mode: WindowManagerPreferenceMode,
  storage: Pick<Storage, "setItem"> | null | undefined = typeof window !== "undefined" ? window.localStorage : null,
): void {
  if (!storage) return
  try {
    storage.setItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY, mode)
  } catch {
    // Quota / private mode — preference is best-effort.
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(GRAVITRE_WM_PREFERENCE_EVENT))
  }
}

/** Same-tab change signal; the native `storage` event only fires in other tabs. */
export const GRAVITRE_WM_PREFERENCE_EVENT = "gravitre:wm-preference"

/**
 * `useSyncExternalStore` subscription. The server snapshot is always `null`, so the
 * first client render matches SSR and the stored preference lands in a follow-up
 * render instead of during hydration.
 */
export function subscribeWindowManagerPreference(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {}
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === GRAVITRE_WM_PREFERENCE_STORAGE_KEY) onChange()
  }
  window.addEventListener("storage", onStorage)
  window.addEventListener(GRAVITRE_WM_PREFERENCE_EVENT, onChange)
  return () => {
    window.removeEventListener("storage", onStorage)
    window.removeEventListener(GRAVITRE_WM_PREFERENCE_EVENT, onChange)
  }
}

export function getWindowManagerPreferenceServerSnapshot(): WindowManagerPreferenceMode | null {
  return null
}

/** Legacy React presentation mode → persistable WM preference (helper is not a preference). */
export function legacyToWindowManagerPreference(
  mode: LegacyPresentationMode,
): WindowManagerPreferenceMode | null {
  switch (mode) {
    case "helper":
      return null
    case "float":
      return "compact"
    case "floating":
      return "floating"
    case "docked":
      return "docked"
    case "expanded":
      return "expanded"
    case "fullscreen":
      return "fullscreen"
  }
}

/**
 * Preference wins when present; otherwise contextual default.
 * `restored` resolves to lastMeaningful (caller-supplied), not a stored default.
 */
export function resolvePreferredWindowMode(args: {
  hints: WindowManagerContextHints
  preference?: WindowManagerPreferenceMode | null
  lastMeaningful?: WindowManagerPreferenceMode | null
  requested?: WindowManagerMode | null
}): WindowManagerPreferenceMode {
  if (args.requested === "restored") {
    return args.lastMeaningful ?? args.preference ?? resolveContextualWindowDefault(args.hints)
  }
  if (args.requested && isWindowManagerPreferenceMode(args.requested)) {
    return args.requested
  }
  if (args.preference && isWindowManagerPreferenceMode(args.preference)) {
    return args.preference
  }
  return resolveContextualWindowDefault(args.hints)
}

/** Pure transition helper — identity object is returned unchanged (reference-stable when same input). */
export function transitionWindowMode<T extends WindowManagerIdentity>(args: {
  from: WindowManagerMode
  to: WindowManagerMode
  identity: T
  lastMeaningful: WindowManagerPreferenceMode
}): {
  mode: Exclude<WindowManagerMode, "restored"> | WindowManagerPreferenceMode
  lastMeaningful: WindowManagerPreferenceMode
  identity: T
} {
  const { from, to, identity, lastMeaningful } = args
  if (to === "restored") {
    return { mode: lastMeaningful, lastMeaningful, identity }
  }
  if (to === "minimized") {
    const remembered =
      from !== "minimized" && from !== "restored" && isWindowManagerPreferenceMode(from)
        ? from
        : lastMeaningful
    return { mode: "minimized", lastMeaningful: remembered, identity }
  }
  if (isWindowManagerPreferenceMode(to)) {
    return { mode: to, lastMeaningful: to, identity }
  }
  return { mode: to, lastMeaningful, identity }
}

/** Map WM preference modes onto legacy React presentation modes for soft integration. */
export function windowManagerModeToLegacy(mode: WindowManagerMode): LegacyPresentationMode {
  switch (mode) {
    case "minimized":
      return "helper"
    case "compact":
      return "float"
    case "floating":
      return "floating"
    case "docked":
      return "docked"
    case "expanded":
      return "expanded"
    case "fullscreen":
      return "fullscreen"
    case "restored":
      return "float"
  }
}
