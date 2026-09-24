"use client"

/**
 * Docked Window Manager shell — side persistence with page context visible.
 * Presentation-only. Does not mount useChat / SSE / voice execution.
 */

import type { PropsWithChildren, ReactNode } from "react"
import { ChatWindowControls, type ChatWindowControlHandlers } from "@/components/gravitre/chat-window-controls"
import { GravitreWindowFrame } from "@/components/gravitre/window-manager/gravitre-window-frame"
import type { WindowManagerIdentity } from "@/lib/gravitre-window-manager"
import { cn } from "@/lib/utils"

export function GravitreDockedShell({
  identity,
  title,
  handlers,
  pageContextSlot,
  children,
  className,
}: PropsWithChildren<{
  identity: WindowManagerIdentity
  title?: ReactNode
  handlers: ChatWindowControlHandlers
  /** Visible page context beside the dock — required for docked composition. */
  pageContextSlot?: ReactNode
  className?: string
}>) {
  return (
    <div
      data-gravitre-docked-shell=""
      className={cn("flex h-full min-h-[320px] w-full overflow-hidden", className)}
    >
      <div className="min-w-0 flex-1 overflow-auto border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]">
        {pageContextSlot ?? (
          <div className="p-6 text-sm text-[color:var(--g-text-muted)]">Page context</div>
        )}
      </div>
      <GravitreWindowFrame
        mode="docked"
        identity={identity}
        title={title}
        className="h-full w-[var(--g-wm-dock-width)] shrink-0 rounded-none border-y-0 border-r-0"
        controls={<ChatWindowControls surface="docked" handlers={handlers} />}
      >
        {children}
      </GravitreWindowFrame>
    </div>
  )
}
