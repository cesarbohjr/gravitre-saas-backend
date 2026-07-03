"use client"

import { cn } from "@/lib/utils"

export type ContextSourcesSummary = {
  connectors?: string[]
  docCount?: number
  memoryCount?: number
}

export function ContextSourcesIndicator({
  sources,
  className,
  onClick,
}: {
  sources: ContextSourcesSummary | null
  className?: string
  onClick?: () => void
}) {
  if (!sources) return null

  const connectors = sources.connectors?.filter(Boolean) ?? []
  const docCount = sources.docCount ?? 0
  const memoryCount = sources.memoryCount ?? 0
  if (connectors.length === 0 && docCount === 0 && memoryCount === 0) return null

  const parts: string[] = []
  if (connectors.length > 0) {
    parts.push(connectors.slice(0, 3).join(" · "))
  }
  if (docCount > 0) {
    parts.push(`${docCount} doc${docCount === 1 ? "" : "s"}`)
  }
  if (memoryCount > 0) {
    parts.push(`${memoryCount} ${memoryCount === 1 ? "memory" : "memories"}`)
  }

  const content = (
    <>
      <span className="font-medium text-foreground/80">Sources:</span> {parts.join(" · ")}
    </>
  )

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex max-w-full items-center rounded-full border border-border/70 bg-muted/40 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground",
          className,
        )}
      >
        {content}
      </button>
    )
  }

  return (
    <p className={cn("text-[11px] text-muted-foreground", className)}>{content}</p>
  )
}
