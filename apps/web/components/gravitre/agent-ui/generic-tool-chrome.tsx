"use client"

/**
 * Agent Elements–inspired GenericTool / McpTool chrome (ADAPT).
 * Collapsible I/O shell around existing tool detail bodies — no AgentChat shell.
 */

import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
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
        "mt-2 overflow-hidden border bg-card text-xs text-foreground",
        RADIUS.card,
        className,
      )}
      data-testid="generic-tool-chrome"
      data-tool={toolName}
    >
      <div
        className={cn(
          "flex h-7 items-center gap-1.5 border-b border-border px-2.5",
          STATUS.idle,
          "rounded-none border-x-0 border-t-0",
        )}
      >
        <Plug className="h-3 w-3 shrink-0" aria-hidden />
        <span className={cn(TYPE.meta, "truncate font-medium")}>{toolName}</span>
      </div>
      <div className="bg-background px-2.5 py-2">{children}</div>
    </div>
  )
}
