"use client"

import { useState } from "react"
import { CaretDown, CaretUp } from "@phosphor-icons/react"
import { entityTypeLabel } from "@/lib/learning-ui-copy"

const LEGEND_TYPES = ["customer", "company", "employee", "agent", "product", "vendor"] as const

export function RelationshipLegend() {
  const [open, setOpen] = useState(false)

  return (
    <div className="pointer-events-auto absolute bottom-3 left-3 z-10 max-w-[220px]">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)]/95 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)] shadow-[var(--np-shadow)] backdrop-blur-sm"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        Legend
        {open ? <CaretUp className="h-3 w-3" aria-hidden /> : <CaretDown className="h-3 w-3" aria-hidden />}
      </button>
      {open ? (
        <div className="mt-1 space-y-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)]/95 p-2.5 text-[10px] text-[color:var(--g-text-secondary)] shadow-[var(--np-shadow)] backdrop-blur-sm">
          <ul className="space-y-1">
            {LEGEND_TYPES.map((t) => (
              <li key={t} className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[color:var(--g-brand)]/70" aria-hidden />
                {entityTypeLabel(t)}
              </li>
            ))}
          </ul>
          <div className="border-t border-divide pt-2 space-y-1">
            <p>── Confirmed entity (you added)</p>
            <p>-- Learned relationship</p>
            <p>-- Needs review (low confidence)</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
