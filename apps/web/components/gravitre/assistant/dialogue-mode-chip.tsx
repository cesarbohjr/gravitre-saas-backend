"use client"

import { cn } from "@/lib/utils"
import { DIALOGUE_MODE_LABELS } from "@/lib/dialogue-mode-labels"

export function DialogueModeChip({
  mode,
  toolActivity,
}: {
  mode?: string | null
  toolActivity?: string | null
}) {
  const resolved =
    toolActivity ??
    (mode ? DIALOGUE_MODE_LABELS[mode] ?? mode.replace(/_/g, " ") : null)
  if (!resolved) return null

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        "border-emerald-200 bg-emerald-50 text-emerald-700",
        "dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
      )}
    >
      {resolved}
    </span>
  )
}
