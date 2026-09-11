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
import {
  NucleoClose,
  NucleoCollapse,
  NucleoExpand,
  NucleoFullscreen,
  NucleoMinimize,
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
  const ids = controlsForSurface(surface)

  return (
    <div className={className ?? "flex items-center gap-0.5"}>
      {leading}
      {ids.map((id) => {
        const onClick = handlers[id]
        // A manifest entry with no handler would render a button that does
        // nothing, which is worse than the missing control it was meant to fix.
        if (!onClick) return null
        const label = CHAT_WINDOW_CONTROL_LABELS[id]
        const Icon = ICONS[id]
        return (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
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
