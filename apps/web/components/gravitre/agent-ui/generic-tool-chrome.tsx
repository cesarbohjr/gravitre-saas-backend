"use client"

/**
 * Agent Elements–inspired GenericTool / McpTool chrome (ADAPT).
 * Collapsible I/O shell around existing tool detail bodies — no AgentChat shell.
 */

import { cn } from "@/lib/utils"
import { STATUS, TYPE } from "@/lib/design-system"
import { Plug } from "lucide-react"

export function GenericToolChrome({
  toolName,
  children,
  className,
}: {
  toolName: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "mt-2 overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] text-xs text-foreground shadow-[var(--np-shadow)]",
        className,
      )}
      data-testid="generic-tool-chrome"
      data-tool={toolName}
    >
      <div
        className={cn(
          "flex h-7 items-center gap-1.5 border-b border-divide px-2.5",
          STATUS.idle,
          "rounded-none border-x-0 border-t-0",
        )}
      >
        <Plug className="h-3 w-3 shrink-0" aria-hidden />
        <span className={cn(TYPE.meta, "truncate font-medium")}>{toolName}</span>
      </div>
      <div className="bg-[color:var(--g-canvas)] px-2.5 py-2">{children}</div>
    </div>
  )
}
