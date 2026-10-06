import { cn } from "@/lib/utils"

export type ActivityStat = {
  label: string
  value: number | null
  tone: "info" | "attention" | "neutral" | "brand"
}

const DOT: Record<ActivityStat["tone"], string> = {
  info: "bg-sky-500",
  attention: "bg-[color:var(--g-approval)]",
  neutral: "bg-muted-foreground/50",
  brand: "bg-[color:var(--g-emerald)]",
}

const ACTIVE: Record<ActivityStat["tone"], string> = {
  info: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
  attention: "bg-[color:var(--g-approval)]/12 text-[color:var(--g-approval)]",
  neutral: "bg-[color:var(--g-surface-2)] text-foreground",
  brand: "bg-[color:var(--g-emerald-pale)] text-[color:var(--g-brand-active)] dark:bg-[color:var(--g-emerald-soft)] dark:text-[color:var(--g-brand)]",
}

/**
 * Counts for the loaded rows as one line of chips beside the view tabs, instead
 * of a row of tall cards that pushed the work itself below the fold. A chip with
 * a non-zero count takes its tone; zero stays quiet.
 */
export function ActivityStatStrip({ items, className }: { items: ActivityStat[]; className?: string }) {
  return (
    <ul
      aria-label="Activity counts in loaded results and current filters"
      title="Counts reflect loaded results and current filters."
      className={cn("flex flex-wrap items-center gap-1.5 pb-2", className)}
      data-testid="activity-stat-strip"
    >
      {items.map((item) => {
        const live = typeof item.value === "number" && item.value > 0
        return (
          <li
            key={item.label}
            className={cn(
              "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[12px]",
              live ? ACTIVE[item.tone] : "text-muted-foreground",
            )}
          >
            <span className={cn("size-1.5 rounded-full", live ? DOT[item.tone] : "bg-muted-foreground/30")} aria-hidden />
            <span className="font-semibold tabular-nums">{item.value == null ? "—" : item.value.toLocaleString()}</span>
            <span>{item.label}</span>
          </li>
        )
      })}
    </ul>
  )
}
