"use client"

/**
 * Gravitre Window Manager — presentation frame (Slice 0).
 * Owns chrome composition only. Identity props are displayed and must stay
 * stable across mode changes; execution state is never created here.
 */

import type { PropsWithChildren, ReactNode } from "react"
import { GRAVITRE_AI_WORKSPACE_LAYOUT_ID } from "@/lib/gravitre-ai-presentation"
import { WINDOW_CHROME } from "@/lib/design-system"
import type { WindowManagerIdentity, WindowManagerMode } from "@/lib/gravitre-window-manager"
import { cn } from "@/lib/utils"

export function GravitreWindowFrame({
  mode,
  identity,
  title = "Ask Gravitre",
  controls,
  children,
  className,
  role = "region",
  "aria-label": ariaLabel,
}: PropsWithChildren<{
  mode: Exclude<WindowManagerMode, "restored">
  identity: WindowManagerIdentity
  title?: ReactNode
  controls?: ReactNode
  className?: string
  role?: "region" | "dialog"
  "aria-label"?: string
}>) {
  return (
    <section
      data-gravitre-window-frame=""
      data-wm-mode={mode}
      data-conversation-id={identity.conversationId ?? undefined}
      data-task-id={identity.taskId ?? undefined}
      data-artifact-id={identity.artifactId ?? undefined}
      data-approval-id={identity.approvalId ?? undefined}
      data-voice-session-id={identity.voiceSessionId ?? undefined}
      data-layout-id={GRAVITRE_AI_WORKSPACE_LAYOUT_ID}
      role={role}
      aria-label={ariaLabel ?? (typeof title === "string" ? title : "Gravitre window")}
      aria-modal={role === "dialog" ? true : undefined}
      className={cn(
        "flex flex-col overflow-hidden rounded-[var(--g-radius-panel)]",
        WINDOW_CHROME.frame,
        className,
      )}
    >
      <header className={WINDOW_CHROME.header}>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-[color:var(--g-text-primary)]">{title}</p>
          <p className={WINDOW_CHROME.identity} data-wm-identity="">
            {[
              identity.conversationId ? `conv ${identity.conversationId}` : null,
              identity.taskId ? `task ${identity.taskId}` : null,
            ]
              .filter(Boolean)
              .join(" · ") || "no conversation"}
          </p>
        </div>
        {controls}
      </header>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  )
}
