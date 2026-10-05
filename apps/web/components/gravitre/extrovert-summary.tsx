import { cn } from "@/lib/utils"

export type ExtrovertSummaryItem = {
  label: string
  value: number | string | null
  tone?: "neutral" | "brand" | "attention"
}

/** Figma 10:25 / 10:121: readable KPI bands that retain every metric on phones. */
export function ExtrovertSummary({ items, label }: { items: ExtrovertSummaryItem[]; label: string }) {
  return (
    <section aria-label={label} className="grid grid-cols-2 gap-2 md:grid-cols-4" data-testid="extrovert-summary">
      {items.map((item) => (
        <div key={item.label} className={cn("min-w-0 rounded-[10px] p-4", item.tone === "brand" ? "bg-[color:var(--g-emerald-pale)]" : item.tone === "attention" ? "bg-[color:color-mix(in_srgb,var(--g-warmth)_10%,white)]" : "bg-[color:var(--g-surface-1)]")}>
          <p className="font-sans text-2xl font-medium tabular-nums text-[color:var(--g-text-primary)]">{item.value == null ? "—" : typeof item.value === "number" ? item.value.toLocaleString() : item.value}</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--g-text-muted)]">{item.label}</p>
        </div>
      ))}
    </section>
  )
}
