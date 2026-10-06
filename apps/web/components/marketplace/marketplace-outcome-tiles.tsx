"use client"

import { ArrowUpRight, HeartHandshake, Megaphone, ServerCog, TrendingUp, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export type OutcomeTile = {
  label: string
  detail: string
  department: string
  count?: number
  tone: "emerald" | "electric" | "coral"
}

const ICONS: Record<string, LucideIcon> = {
  "Run IT": ServerCog,
  "Grow Revenue": TrendingUp,
  "Market Smarter": Megaphone,
  "Serve Customers": HeartHandshake,
}

const TONE: Record<OutcomeTile["tone"], string> = {
  emerald:
    "bg-[color:color-mix(in_srgb,var(--g-emerald)_16%,transparent)] text-[color:var(--g-emerald)]",
  electric:
    "bg-[color:color-mix(in_srgb,var(--g-electric)_16%,transparent)] text-[color:var(--g-electric)]",
  coral:
    "bg-[color:color-mix(in_srgb,var(--g-warmth)_16%,transparent)] text-[color:var(--g-warmth)]",
}

/** Outcome-led entry points that filter the catalog to one department. */
export function MarketplaceOutcomeTiles({
  tiles,
  activeDepartment,
  onSelect,
}: {
  tiles: OutcomeTile[]
  activeDepartment: string | null
  onSelect: (department: string | null) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Browse by outcome" role="group">
      {tiles.map((tile) => {
        const Icon = ICONS[tile.label] ?? ArrowUpRight
        const active = activeDepartment?.toLowerCase() === tile.department.toLowerCase()
        return (
          <button
            key={tile.label}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(active ? null : tile.department)}
            className={cn(
              "group flex min-h-24 flex-col items-start gap-3 rounded-xl border bg-[color:var(--g-surface-1)] p-3.5 text-left transition-[border-color,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-safe:hover:-translate-y-0.5 sm:p-4",
              active
                ? "border-[color:var(--g-emerald)] ring-1 ring-[color:var(--g-emerald)]"
                : "border-[color:var(--g-border-default)] hover:border-[color:var(--g-text-muted)]",
            )}
          >
            <span className="flex w-full items-center justify-between">
              <span className={cn("flex size-9 items-center justify-center rounded-lg", TONE[tile.tone])}>
                <Icon className="size-[18px]" strokeWidth={1.75} aria-hidden />
              </span>
              {typeof tile.count === "number" ? (
                <span className="text-xs tabular-nums text-[color:var(--g-text-muted)]">
                  {tile.count} {tile.count === 1 ? "listing" : "listings"}
                </span>
              ) : null}
            </span>
            <span className="min-w-0">
              <span className="block text-[14px] font-semibold text-[color:var(--g-text-primary)]">
                {tile.label}
              </span>
              <span className="mt-0.5 block text-xs leading-5 text-[color:var(--g-text-muted)]">
                {tile.detail}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
