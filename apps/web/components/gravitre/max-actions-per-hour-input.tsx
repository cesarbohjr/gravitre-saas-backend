"use client"

import { useEffect, useId, useState } from "react"
import { MAX_ACTIONS_PER_HOUR_LIMIT, normalizeMaxActionsPerHour } from "@/lib/agent-config-catalog"

/** Number field for the "Slow down" rule. Commits a clamped value on blur. */
export function MaxActionsPerHourInput({
  value,
  onChange,
}: {
  value: number
  onChange: (value: number) => void
}) {
  const id = useId()
  const [draft, setDraft] = useState(String(value))
  useEffect(() => setDraft(String(value)), [value])
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-secondary/40 px-3 py-2">
      <label htmlFor={id} className="text-sm text-foreground">
        Max actions per hour
      </label>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={1}
        max={MAX_ACTIONS_PER_HOUR_LIMIT}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          const next = normalizeMaxActionsPerHour(draft)
          setDraft(String(next))
          if (next !== value) onChange(next)
        }}
        className="h-9 w-24 rounded-md border border-border bg-card px-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <span className="text-xs text-muted-foreground">
        Further actions are refused until the hour resets.
      </span>
    </div>
  )
}
