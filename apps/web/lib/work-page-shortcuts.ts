export const WORK_SHORTCUT_EVENT = "gravitre:work-shortcut"
export const FOCUS_SEARCH_AFTER_NAV_KEY = "gravitre:focus-search-on-load"

import { APP_ROUTES } from "@/lib/app-routes"

export const WORK_SECTION_PATH_PREFIXES = [
  APP_ROUTES.universalSearch,
  APP_ROUTES.gravitreAi,
  APP_ROUTES.agents,
  APP_ROUTES.multiAgentRun,
  "/assignments",
] as const

export type WorkShortcutAction = "new" | "focus-search"

export function dispatchWorkShortcut(action: WorkShortcutAction) {
  if (typeof window === "undefined") return
  window.dispatchEvent(
    new CustomEvent(WORK_SHORTCUT_EVENT, { detail: { action } }),
  )
}

export function markFocusSearchAfterNav() {
  if (typeof window === "undefined") return
  sessionStorage.setItem(FOCUS_SEARCH_AFTER_NAV_KEY, "1")
}

export function consumeFocusSearchAfterNav(): boolean {
  if (typeof window === "undefined") return false
  if (sessionStorage.getItem(FOCUS_SEARCH_AFTER_NAV_KEY) !== "1") return false
  sessionStorage.removeItem(FOCUS_SEARCH_AFTER_NAV_KEY)
  return true
}

export function isWorkSectionPath(pathname: string): boolean {
  return WORK_SECTION_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) return true
  return Boolean(target.closest("[contenteditable='true']"))
}
