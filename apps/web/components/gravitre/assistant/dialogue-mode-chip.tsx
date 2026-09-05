"use client"

import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { DIALOGUE_MODE_LABELS } from "@/lib/dialogue-mode-labels"

export function DialogueModeChip({
  mode,
  toolActivity,
  className,
}: {
  mode?: string | null
  toolActivity?: string | null
  className?: string
}) {
  const resolved =
    toolActivity ??
    (mode ? DIALOGUE_MODE_LABELS[mode] ?? mode.replace(/_/g, " ") : null)
  if (!resolved) return null

  const tone =
    mode === "clarify" || mode === "confirm" || mode === "awaiting_approval"
      ? STATUS.pending
      : mode === "execute" || mode === "tool"
        ? STATUS.running
        : STATUS.idle

  return (
    <span
      className={cn(
        "inline-flex items-center border px-2.5 py-0.5 font-medium",
        RADIUS.control,
        TYPE.meta,
        tone,
        className,
      )}
    >
      {resolved}
    </span>
  )
}
