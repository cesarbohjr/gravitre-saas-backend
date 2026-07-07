/** Shared slide timing for chat history (left) and activity/Meson (right) panels. */
export const WORKSPACE_PANEL_SLIDE_MS = 300
export const WORKSPACE_PANEL_SLIDE_EASE = "ease-in-out" as const

export const workspacePanelAsideClasses = (open: boolean) =>
  [
    "relative shrink-0 overflow-hidden transition-[width,opacity,border-color] duration-300 ease-in-out",
    open ? "opacity-100" : "w-0 min-w-0 max-w-0 opacity-0 border-transparent pointer-events-none",
  ] as const
