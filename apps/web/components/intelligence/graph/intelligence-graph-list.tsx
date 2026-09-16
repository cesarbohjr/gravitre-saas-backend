"use client"

import type { MapTopology } from "@/components/intelligence/map/map-topology"
import { accessibleGraphRows } from "@/lib/intelligence/graph/accessible-graph-list"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function IntelligenceGraphList({
  topology,
  selectedId,
  onSelect,
}: {
  topology: MapTopology
  selectedId?: string | null
  onSelect: (nodeId: string) => void
}) {
  const rows = accessibleGraphRows(topology)

  return (
    <div
      className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3"
      data-testid="intelligence-graph-list"
    >
      <p className={TYPE.eyebrow}>Graph list</p>
      <p className={cn(TYPE.meta, "mt-0.5")}>
        Same snapshot nodes as the canvas — keyboard-readable without shrinking the map.
      </p>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No nodes in this lens yet.</p>
      ) : (
        <ul className="mt-3 max-h-[56vh] space-y-1 overflow-y-auto" role="list">
          {rows.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={cn(
                  "flex w-full flex-col rounded-md px-3 py-2 text-left text-sm hover:bg-[color:var(--g-surface-2)]",
                  selectedId === row.id && "bg-[color:var(--g-intelligence-surface)]/40 ring-1 ring-[color:var(--g-brand)]",
                )}
                aria-current={selectedId === row.id ? "true" : undefined}
                onClick={() => onSelect(row.id)}
              >
                <span className="font-medium">{row.label}</span>
                <span className={TYPE.meta}>
                  {row.kind}
                  {row.sublabel ? ` · ${row.sublabel}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
