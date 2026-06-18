"use client"

import { cn } from "@/lib/utils"
import type { MarketplaceFacetCount } from "@/types/api"

function FacetGroup({
  label,
  items,
  activeKey,
  onSelect,
}: {
  label: string
  items: MarketplaceFacetCount[]
  activeKey: string | null
  onSelect: (key: string | null) => void
}) {
  if (!items.length) return null
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <ul className="space-y-1">
        <li>
          <button
            type="button"
            onClick={() => onSelect(null)}
            className={cn(
              "w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors",
              activeKey == null
                ? "bg-primary/10 font-medium text-primary"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
            )}
          >
            All
          </button>
        </li>
        {items.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              onClick={() => onSelect(item.key)}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                activeKey === item.key
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              <span className="truncate capitalize">{item.key.replace(/_/g, " ")}</span>
              <span className="shrink-0 tabular-nums text-xs">{item.count}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function MarketplaceFacetSidebar({
  totalAssets,
  departments,
  categories,
  activeDepartment,
  activeCategory,
  onDepartmentChange,
  onCategoryChange,
  className,
}: {
  totalAssets: number
  departments: MarketplaceFacetCount[]
  categories: MarketplaceFacetCount[]
  activeDepartment: string | null
  activeCategory: string | null
  onDepartmentChange: (key: string | null) => void
  onCategoryChange: (key: string | null) => void
  className?: string
}) {
  return (
    <aside className={cn("w-52 shrink-0 space-y-5", className)}>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Catalog</p>
        <p className="text-2xl font-semibold tabular-nums">{totalAssets}</p>
      </div>
      <FacetGroup
        label="Departments"
        items={departments}
        activeKey={activeDepartment}
        onSelect={onDepartmentChange}
      />
      <FacetGroup
        label="Categories"
        items={categories}
        activeKey={activeCategory}
        onSelect={onCategoryChange}
      />
    </aside>
  )
}
