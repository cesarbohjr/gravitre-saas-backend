"use client"

import { Check, ChevronDown, SlidersHorizontal, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { HUB_TABS } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export type CatalogTypeOption = {
  id: string
  label: string
  count?: number
  primary: boolean
}

export type CatalogDepartmentOption = { key: string; count: number }

const PRICE_LABELS: Record<string, string> = {
  all: "Any price",
  free: "Free",
  paid: "Paid",
}

function humanize(value: string) {
  const text = value.replace(/_/g, " ")
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/**
 * Catalog controls: a short row of primary listing types with the long tail
 * behind "More", plus department and price as compact dropdowns.
 */
export function MarketplaceCatalogToolbar({
  types,
  typeValue,
  onTypeChange,
  departments,
  departmentValue,
  onDepartmentChange,
  priceValue,
  onPriceChange,
  hasFilters,
  onClear,
}: {
  types: CatalogTypeOption[]
  typeValue: string
  onTypeChange: (id: string) => void
  departments: CatalogDepartmentOption[]
  departmentValue: string | null
  onDepartmentChange: (key: string | null) => void
  priceValue: string
  onPriceChange: (value: "all" | "free" | "paid") => void
  hasFilters: boolean
  onClear: () => void
}) {
  const primary = types.filter((type) => type.primary)
  const overflow = types.filter((type) => !type.primary)
  const activeOverflow = overflow.find((type) => type.id === typeValue)

  return (
    <div className="flex flex-col gap-3 border-b border-[color:var(--g-border-subtle)] md:flex-row md:items-end md:justify-between">
      <div role="group" aria-label="Listing type" className={cn(HUB_TABS.nav, "min-w-0")}>
        {primary.map((type) => (
          <button
            key={type.id}
            type="button"
            aria-pressed={typeValue === type.id}
            onClick={() => onTypeChange(type.id)}
            className={cn(
              HUB_TABS.link,
              typeValue === type.id ? HUB_TABS.active : HUB_TABS.idle,
            )}
          >
            {type.label}
            {typeof type.count === "number" ? (
              <span className="ml-1.5 tabular-nums text-[color:var(--g-text-muted)]">
                {type.count}
              </span>
            ) : null}
          </button>
        ))}
        {overflow.length > 0 ? (
          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                HUB_TABS.link,
                "gap-1",
                activeOverflow ? HUB_TABS.active : HUB_TABS.idle,
              )}
            >
              {activeOverflow ? activeOverflow.label : "More"}
              <ChevronDown className="mb-0.5 size-3.5" aria-hidden />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
                More listing types
              </DropdownMenuLabel>
              <DropdownMenuRadioGroup value={typeValue} onValueChange={onTypeChange}>
                {overflow.map((type) => (
                  <DropdownMenuRadioItem
                    key={type.id}
                    value={type.id}
                    className="min-h-11 md:min-h-9"
                  >
                    <span className="flex-1">{type.label}</span>
                    {typeof type.count === "number" ? (
                      <span className="tabular-nums text-xs text-muted-foreground">
                        {type.count}
                      </span>
                    ) : null}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2 pb-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "min-h-11 gap-1.5 md:min-h-8",
                departmentValue && "border-[color:var(--g-emerald)] text-foreground",
              )}
            >
              <SlidersHorizontal className="size-3.5" aria-hidden />
              {departmentValue ? humanize(departmentValue) : "All departments"}
              <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-80 w-60 overflow-y-auto">
            <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
              Department
            </DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={departmentValue ?? "__all"}
              onValueChange={(value) =>
                onDepartmentChange(value === "__all" ? null : value)
              }
            >
              <DropdownMenuRadioItem value="__all" className="min-h-11 md:min-h-9">
                All departments
              </DropdownMenuRadioItem>
              <DropdownMenuSeparator />
              {departments.map((facet) => (
                <DropdownMenuRadioItem
                  key={facet.key}
                  value={facet.key}
                  className="min-h-11 md:min-h-9"
                >
                  <span className="flex-1">{humanize(facet.key)}</span>
                  <span className="tabular-nums text-xs text-muted-foreground">
                    {facet.count}
                  </span>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(
                "min-h-11 gap-1.5 md:min-h-8",
                priceValue !== "all" && "border-[color:var(--g-emerald)] text-foreground",
              )}
            >
              {PRICE_LABELS[priceValue] ?? "Any price"}
              <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            {(["all", "free", "paid"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => onPriceChange(value)}
                className="flex min-h-11 w-full items-center gap-2 rounded-sm px-2 text-left text-sm hover:bg-accent focus-visible:bg-accent focus-visible:outline-none md:min-h-9"
              >
                <Check
                  className={cn("size-4", priceValue === value ? "opacity-100" : "opacity-0")}
                  aria-hidden
                />
                {PRICE_LABELS[value]}
              </button>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {hasFilters ? (
          <Button variant="ghost" size="sm" onClick={onClear} className="min-h-11 gap-1 text-muted-foreground md:min-h-8">
            <X className="size-3.5" aria-hidden />
            Clear
          </Button>
        ) : null}
      </div>
    </div>
  )
}
