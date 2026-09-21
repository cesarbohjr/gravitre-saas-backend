"use client"

import { useMemo } from "react"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import { INTELLIGENCE_MAP_LENSES } from "@/components/intelligence/map/intelligence-map-lens"
import type { CanonicalGraphNode } from "@/lib/intelligence/canonical-graph-topology"
import {
  buildIntelligenceMatrix,
  INTELLIGENCE_MATRIX_ROWS,
  matrixCellKey,
  type IntelligenceMatrixRowId,
} from "@/lib/intelligence/build-intelligence-matrix"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export function IntelligenceMatrixLens({
  graphNodes,
  selectedCellKey,
  onSelectCell,
  onOpenFieldView,
  className,
}: {
  graphNodes: CanonicalGraphNode[] | undefined | null
  selectedCellKey: string | null
  onSelectCell: (key: string | null, lens: IntelligenceMapLens, nodeIds: string[]) => void
  onOpenFieldView?: (lens: IntelligenceMapLens) => void
  className?: string
}) {
  const model = useMemo(() => buildIntelligenceMatrix(graphNodes), [graphNodes])
  const selectedCell = selectedCellKey ? model.byKey.get(selectedCellKey) : null

  return (
    <div className={cn("space-y-3", className)} data-testid="intel-i3-matrix">
      <p className={cn(TYPE.meta, "text-[color:var(--g-text-muted)]")}>
        Matrix lens — scan density by domain and lens. Select a cell for detail; field view opens the full graph.
      </p>

      <div className="overflow-x-auto rounded-lg border border-[color:var(--g-border-subtle)]">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)]/50">
              <th scope="col" className={cn(TYPE.eyebrow, "px-3 py-2")}>
                Domain
              </th>
              {INTELLIGENCE_MAP_LENSES.map((lens) => (
                <th key={lens.id} scope="col" className={cn(TYPE.eyebrow, "px-3 py-2 capitalize")}>
                  {lens.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {INTELLIGENCE_MATRIX_ROWS.map((row) => (
              <tr key={row.id} className="border-b border-[color:var(--g-border-subtle)] last:border-0">
                <th scope="row" className="px-3 py-2 font-medium text-[color:var(--g-text-primary)]">
                  {row.label}
                </th>
                {INTELLIGENCE_MAP_LENSES.map((lens) => {
                  const key = matrixCellKey(row.id, lens.id)
                  const cell = model.byKey.get(key)!
                  const active = selectedCellKey === key
                  return (
                    <td key={key} className="p-1">
                      <button
                        type="button"
                        aria-pressed={active}
                        data-testid={`intel-matrix-cell-${row.id}-${lens.id}`}
                        className={cn(
                          "flex min-h-[52px] w-full flex-col rounded-md px-2 py-1.5 text-left transition-colors",
                          active
                            ? "bg-[color:var(--g-intelligence-soft)] ring-1 ring-[color:var(--g-intelligence)]"
                            : "hover:bg-[color:var(--g-surface-2)]",
                        )}
                        onClick={() =>
                          onSelectCell(active ? null : key, lens.id, cell.nodeIds)
                        }
                      >
                        <span className="text-sm font-semibold tabular-nums text-[color:var(--g-text-primary)]">
                          {cell.count > 0 ? cell.count : "—"}
                        </span>
                        {cell.topSignal ? (
                          <span className={cn(TYPE.meta, "line-clamp-2")}>{cell.topSignal}</span>
                        ) : null}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedCell && selectedCell.count > 0 ? (
        <div
          className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4"
          data-testid="intel-i3-cell-panel"
        >
          <p className={TYPE.eyebrow}>
            {INTELLIGENCE_MATRIX_ROWS.find((r) => r.id === selectedCell.rowId)?.label} ·{" "}
            {INTELLIGENCE_MAP_LENSES.find((l) => l.id === selectedCell.lens)?.label}
          </p>
          <p className={cn(TYPE.meta, "mt-1")}>
            {selectedCell.count} node{selectedCell.count === 1 ? "" : "s"} in this intersection
            {selectedCell.topSignal ? ` · ${selectedCell.topSignal}` : ""}
          </p>
          {onOpenFieldView ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-3"
              data-testid="intel-i3-open-field"
              onClick={() => onOpenFieldView(selectedCell.lens)}
            >
              Open field view
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export type { IntelligenceMatrixRowId }
