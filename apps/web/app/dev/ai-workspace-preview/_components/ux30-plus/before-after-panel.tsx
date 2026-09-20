"use client"

import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type Change = {
  action: "removed" | "consolidated" | "contextual" | "visual" | "clearer"
  detail: string
}

export function BeforeAfterPanel({
  surface,
  changes,
}: {
  surface: "intelligence" | "activity" | "navigation"
  changes: Change[]
}) {
  const titles = {
    intelligence: "Intelligence — before → harness concept",
    activity: "Activity — before → harness concept",
    navigation: "Navigation — before → harness concept",
  }

  return (
    <aside className="mt-6 rounded-xl border border-dashed border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-4">
      <p className={TYPE.eyebrow}>{titles[surface]}</p>
      <ul className="mt-3 space-y-2">
        {changes.map((c) => (
          <li key={c.detail} className={cn(TYPE.bodyMuted, "text-sm")}>
            <span className="font-medium capitalize text-[color:var(--g-text-primary)]">{c.action}:</span>{" "}
            {c.detail}
          </li>
        ))}
      </ul>
    </aside>
  )
}
