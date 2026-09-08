"use client"

import { useMemo, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { NucleoSearch } from "@/components/icons/nucleo/semantic"
import {
  KPI_CATEGORIES,
  pickableKpis,
  type KpiDefinition,
} from "@/lib/dashboard/kpi-registry"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

export function KpiPickerDialog({
  open,
  onOpenChange,
  displayedMetricIds,
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  displayedMetricIds: Set<string>
  onAdd: (metricId: string) => void
}) {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState<string>("recommended")

  const kpis = useMemo(() => {
    const all = pickableKpis()
    const q = query.trim().toLowerCase()
    return all.filter((kpi) => {
      if (category === "recommended" && !kpi.recommended) return false
      if (category === "displayed" && !displayedMetricIds.has(kpi.id)) return false
      if (category === "available" && displayedMetricIds.has(kpi.id)) return false
      if (
        category !== "recommended" &&
        category !== "displayed" &&
        category !== "available" &&
        kpi.category !== category
      ) {
        return false
      }
      if (!q) return true
      return (
        kpi.name.toLowerCase().includes(q) ||
        kpi.description.toLowerCase().includes(q) ||
        kpi.category.includes(q) ||
        kpi.dataSource.toLowerCase().includes(q)
      )
    })
  }, [category, displayedMetricIds, query])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-divide px-4 py-3 text-left">
          <DialogTitle className={TYPE.sectionTitle}>Add KPI</DialogTitle>
          <DialogDescription className={TYPE.meta}>
            Choose from metrics grounded in live Gravitre data. No fabricated values.
          </DialogDescription>
        </DialogHeader>

        <div className="border-b border-divide px-4 py-2.5">
          <div className="relative">
            <NucleoSearch className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search KPIs…"
              className="h-9 pl-8"
              aria-label="Search KPIs"
            />
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {[
              { id: "recommended", label: "Recommended" },
              { id: "displayed", label: "Currently displayed" },
              { id: "available", label: "Available" },
              ...KPI_CATEGORIES,
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setCategory(tab.id)}
                className={cn(
                  "rounded-md px-2 py-1 text-[11px] font-medium transition-colors",
                  category === tab.id
                    ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {kpis.length === 0 ? (
            <p className={cn(TYPE.meta, "px-2 py-6 text-center")}>No matching KPIs.</p>
          ) : (
            <ul className="space-y-1">
              {kpis.map((kpi) => (
                <KpiRow
                  key={kpi.id}
                  kpi={kpi}
                  displayed={displayedMetricIds.has(kpi.id)}
                  onAdd={() => {
                    onAdd(kpi.id)
                    onOpenChange(false)
                  }}
                />
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function KpiRow({
  kpi,
  displayed,
  onAdd,
}: {
  kpi: KpiDefinition
  displayed: boolean
  onAdd: () => void
}) {
  return (
    <li className="flex items-start gap-3 rounded-[var(--np-radius-md)] px-2 py-2 hover:bg-muted/50">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-foreground">{kpi.name}</p>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {kpi.category}
          </span>
          {displayed ? (
            <span className="text-[10px] font-medium text-[color:var(--brand)]">On dashboard</span>
          ) : null}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{kpi.description}</p>
        <p className="mt-1 text-[10px] text-muted-foreground/80">
          Source: {kpi.dataSource} · Viz: {kpi.allowedViz.join(", ")}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        variant={displayed ? "outline" : "default"}
        className="h-8 shrink-0"
        disabled={displayed}
        onClick={onAdd}
      >
        {displayed ? "Added" : "Add"}
      </Button>
    </li>
  )
}
