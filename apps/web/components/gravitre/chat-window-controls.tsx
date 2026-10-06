"use client"

/**
 * The one implementation of the AI chat window controls.
 *
 * These buttons existed three times over -- ai-floating-workspace.tsx,
 * ai-workspace-shell.tsx and ai-mobile-sheet.tsx each built their own near-identical
 * group -- and they drifted: the float window never offered fullscreen, the mobile
 * sheet reused one button for two different actions, and the `/ai` page ended up
 * with no window controls at all. Which buttons appear is now decided by
 * CHAT_WINDOW_CONTROLS in lib/chat-window-state.ts, so a surface cannot quietly
 * lose its way out.
 *
 * Styling deliberately matches what those three already rendered (ghost icon
 * Button, h-7 w-7, 3.5 icons) so this is a consolidation and not a redesign.
 */

import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { TOUCH_ICON_BUTTON } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  NucleoClose,
  NucleoCollapse,
  NucleoExpand,
  NucleoFullscreen,
  NucleoMinimize,
  NucleoPanelToggle,
} from "@/components/icons/nucleo/semantic"
import {
  CHAT_WINDOW_CONTROL_LABELS,
  controlsForSurface,
  type ChatSurface,
  type ChatWindowControlId,
} from "@/lib/chat-window-state"

export type ChatWindowControlHandlers = Partial<Record<ChatWindowControlId, () => void>>

const ICONS: Record<ChatWindowControlId, (props: { className?: string }) => ReactNode> = {
  expand: (p) => <NucleoExpand {...p} />,
  collapseToFloat: (p) => <NucleoMinimize {...p} />,
  fullscreen: (p) => <NucleoFullscreen {...p} />,
  exitFullscreen: (p) => <NucleoCollapse {...p} />,
  minimizeToHelper: (p) => <NucleoClose {...p} />,
  openAsFloat: (p) => <NucleoExpand {...p} />,
  dock: (p) => <NucleoPanelToggle {...p} />,
  undock: (p) => <NucleoPanelToggle {...p} />,
}

export function ChatWindowControls({
  surface,
  handlers,
  leading,
  className,
}: {
  surface: ChatSurface
  handlers: ChatWindowControlHandlers
  /** Surface-specific extras that sit in the same group (e.g. the shell's panel toggles). */
  leading?: ReactNode
  className?: string
}) {
  // A manifest entry with no handler would render a button that does nothing,
  // which is worse than the missing control it was meant to fix.
  const ids = controlsForSurface(surface).filter((id) => handlers[id])
  const layoutIds = ids.filter((id) => id !== "minimizeToHelper")
  const hasClose = ids.includes("minimizeToHelper")

  // Three groups, left to right: panels (leading), window layout, close. The
  // dividers let the eye find "close" without scanning a row of look-alike icons.
  const divider = <span aria-hidden className="mx-1 h-4 w-px shrink-0 bg-[color:var(--g-border-default)]" />

  return (
    <div className={className ?? "flex flex-wrap items-center justify-end gap-0.5"}>
      {leading}
      {leading && layoutIds.length > 0 ? divider : null}
      {[...layoutIds, ...(hasClose ? (["minimizeToHelper"] as const) : [])].map((id) => {
        const onClick = handlers[id]!
        const label = CHAT_WINDOW_CONTROL_LABELS[id]
        const Icon = ICONS[id]
        return (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={cn(TOUCH_ICON_BUTTON, "h-11 w-11")}
                aria-label={label}
                data-chat-window-control={id}
                onClick={onClick}
              >
                {Icon({ className: "h-3.5 w-3.5" })}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{label}</TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}
