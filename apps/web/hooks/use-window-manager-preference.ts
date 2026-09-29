"use client"

import { useSyncExternalStore } from "react"
import {
  getWindowManagerPreferenceServerSnapshot,
  readWindowManagerPreference,
  subscribeWindowManagerPreference,
  type WindowManagerPreferenceMode,
} from "@/lib/gravitre-window-manager"

/**
 * Remembered Window Manager preference, hydration-safe.
 *
 * Server render and the hydrating client render both see `null` (the server
 * snapshot), so markup never depends on localStorage. React then re-renders with
 * the stored value immediately after hydration — no effect-driven setState, no
 * `suppressHydrationWarning`.
 */
export function useWindowManagerPreference(): WindowManagerPreferenceMode | null {
  return useSyncExternalStore(
    subscribeWindowManagerPreference,
    () => readWindowManagerPreference(),
    getWindowManagerPreferenceServerSnapshot,
  )
}
