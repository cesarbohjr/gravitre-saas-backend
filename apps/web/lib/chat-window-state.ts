/**
 * One canonical description of the AI chat window's modes, its transitions, and
 * which controls each mode must render.
 *
 * Why a pure module rather than logic inside the shells: the controls were
 * implemented three times (floating window, expanded/fullscreen shell, mobile
 * sheet), and they drifted. The `/ai` full-page surface ended up with no window
 * controls at all, which is how a visible chat surface became impossible to
 * reduce or close. Describing the manifest in one testable place makes that class
 * of drift a test failure instead of a bug report.
 *
 * Vocabulary note. The spec for this work names the states CLOSED / MINIMIZED /
 * COMPACT / WINDOWED / EXPANDED / FULLSCREEN. This codebase already ships
 * `GravitrePresentationMode` as "helper" | "float" | "expanded" | "fullscreen"
 * plus a separate `floatWorkspaceOpen` flag, and those names appear across many
 * components and tests. Renaming them would be a large, risky change that buys
 * nothing functional, so the existing names are kept and mapped here:
 *
 *   CLOSED / MINIMIZED -> floatWorkspaceOpen === false (launcher visible)
 *   WINDOWED           -> "float"
 *   EXPANDED           -> "expanded"
 *   FULLSCREEN         -> "fullscreen"
 *   embedded           -> on /ai with floatWorkspaceOpen === false (page IS the chat)
 *
 * COMPACT has no separate mode; the float window is resizable and covers it.
 */

/** Matches GravitrePresentationMode in ai-workspace-provider.tsx. */
export type ChatWindowMode = "helper" | "float" | "expanded" | "fullscreen"

/**
 * Every surface that can be on screen. `embedded` is not a presentation mode --
 * it is the `/ai` page rendering the chat inline -- but it is a visible chat
 * surface, so it is bound by the same "must have an exit" rule.
 */
/**
 * The mobile sheet deliberately has no entry of its own: it reuses the same
 * per-mode surfaces as the desktop shells, which is what stops the two from
 * drifting apart the way they already had.
 */
export type ChatSurface = "float" | "expanded" | "fullscreen" | "embedded"

export type ChatWindowControlId =
  | "expand"
  | "collapseToFloat"
  | "fullscreen"
  | "exitFullscreen"
  | "minimizeToHelper"
  | "openAsFloat"

/**
 * Controls that leave the user somewhere else they can act from. A surface with
 * none of these is the dead-end this module exists to prevent.
 *
 * Note that in this product "close" and "minimize to helper" are the same
 * action: the window closes to the floating launcher and the conversation is
 * preserved. There is deliberately no separate destructive close here, because
 * discarding a conversation is a product decision nobody asked for.
 */
const EXIT_CONTROLS: readonly ChatWindowControlId[] = [
  "collapseToFloat",
  "exitFullscreen",
  "minimizeToHelper",
  "openAsFloat",
]

/**
 * Which controls each surface renders. This is the single source of truth that
 * <ChatWindowControls /> reads, so the three shells cannot drift apart again.
 */
export const CHAT_WINDOW_CONTROLS: Record<ChatSurface, readonly ChatWindowControlId[]> = {
  // Windowed. Fullscreen is reachable directly rather than only via expanded,
  // which previously forced a two-step trip.
  float: ["expand", "fullscreen", "minimizeToHelper"],
  expanded: ["collapseToFloat", "fullscreen", "minimizeToHelper"],
  fullscreen: ["exitFullscreen", "collapseToFloat", "minimizeToHelper"],
  // The /ai page. It shipped with no window controls, and because /ai also hides
  // the floating launcher by design, that was a surface with no exit at all.
  // "Open as floating window" is the exit: it produces a window that has the
  // full set.
  embedded: ["openAsFloat"],
}

export const CHAT_WINDOW_CONTROL_LABELS: Record<ChatWindowControlId, string> = {
  expand: "Expand",
  collapseToFloat: "Collapse to floating window",
  fullscreen: "Fullscreen",
  exitFullscreen: "Exit fullscreen",
  minimizeToHelper: "Minimize to helper",
  openAsFloat: "Open as floating window",
}

export function controlsForSurface(surface: ChatSurface): readonly ChatWindowControlId[] {
  return CHAT_WINDOW_CONTROLS[surface]
}

/** True when the surface offers at least one way out. */
export function surfaceHasExit(surface: ChatSurface): boolean {
  return controlsForSurface(surface).some((id) => EXIT_CONTROLS.includes(id))
}

export function isExitControl(id: ChatWindowControlId): boolean {
  return EXIT_CONTROLS.includes(id)
}

/**
 * Where the launcher should put the user when they reopen the chat.
 *
 * The old behaviour discarded this: closing to the helper set the mode to
 * "expanded" regardless of what the user had been in, and the launcher then
 * always opened "float". So a user working in fullscreen was returned to a small
 * window, and a user in a small window could not be returned to it at all.
 *
 * "helper" is not a restore target -- restoring to the launcher would be a no-op
 * that looks like the click did nothing -- so it falls back to the windowed mode.
 */
export function restoreTargetMode(previous: ChatWindowMode | null | undefined): ChatWindowMode {
  if (!previous || previous === "helper") return "float"
  return previous
}

/**
 * The mode to remember when closing to the launcher. Recording "helper" would
 * lose the information the restore depends on.
 */
export function modeToRemember(current: ChatWindowMode): ChatWindowMode {
  return current === "helper" ? "float" : current
}
