"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { describeStatus, TONE_BADGE_CLASS } from "@/lib/intelligence/status-language"

/**
 * Phase 2.5 — the one shared place a real technical model/lifecycle status
 * gets rendered to a user. Never renders a bare status word: always pairs
 * the honest, business-friendly phrase with a one-line context sentence
 * (visibly in the same view by default, or as a title tooltip for very
 * dense rows where the surrounding card already carries context).
 */
export function ModelStatusBadge({
  status,
  size = "default",
  showDetail = true,
  className,
}: {
  status: string | null | undefined
  size?: "default" | "sm"
  showDetail?: boolean
  className?: string
}) {
  const { phrase, detail, tone } = describeStatus(status)
  return (
    <span className={cn("inline-flex flex-col items-start gap-1", className)}>
      <Badge
        variant="outline"
        title={detail || undefined}
        className={cn(
          size === "sm" ? "h-5 px-1.5 text-[10px]" : "text-xs",
          TONE_BADGE_CLASS[tone],
        )}
      >
        {phrase}
      </Badge>
      {showDetail && detail ? (
        <span className="text-[11px] leading-snug text-muted-foreground">{detail}</span>
      ) : null}
    </span>
  )
}
