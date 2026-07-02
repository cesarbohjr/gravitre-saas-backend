"use client"

import { useCallback, useState, type ReactNode } from "react"
import { GripVertical } from "lucide-react"
import { cn } from "@/lib/utils"

export type ResultBlockId = "stats" | "analysis" | "results" | "prevention" | "actions" | "plan"

export type LayoutColumn = "main" | "rail"

export const RESULT_BLOCK_CATALOG: { id: ResultBlockId; label: string }[] = [
  { id: "stats", label: "Status" },
  { id: "analysis", label: "AI Analysis" },
  { id: "results", label: "Results" },
  { id: "prevention", label: "Prevention" },
  { id: "actions", label: "Meson Suggested Actions" },
  { id: "plan", label: "Execution Plan" },
]

export const DEFAULT_RESULT_BLOCK_ORDER: ResultBlockId[] = [
  "stats",
  "analysis",
  "results",
  "prevention",
  "actions",
  "plan",
]

type DraggableResultStackProps = {
  order: ResultBlockId[]
  enabledBlocks?: ResultBlockId[]
  onReorder: (next: ResultBlockId[]) => void
  blocks: Record<ResultBlockId, ReactNode>
  className?: string
  column?: LayoutColumn
  onMoveBlockToColumn?: (blockId: ResultBlockId, target: LayoutColumn) => void
  compact?: boolean
}

export function DraggableResultStack({
  order,
  enabledBlocks,
  onReorder,
  blocks,
  className,
  column = "main",
  onMoveBlockToColumn,
  compact = false,
}: DraggableResultStackProps) {
  const [draggingId, setDraggingId] = useState<ResultBlockId | null>(null)
  const [overId, setOverId] = useState<ResultBlockId | null>(null)
  const [peerDropActive, setPeerDropActive] = useState(false)
  const enabledSet = new Set(enabledBlocks ?? order)
  const visibleOrder = order.filter((blockId) => enabledSet.has(blockId))
  const peerColumn: LayoutColumn = column === "main" ? "rail" : "main"
  const peerLabel = column === "main" ? "Move to right panel" : "Move to center page"

  const moveBlock = useCallback(
    (from: ResultBlockId, to: ResultBlockId) => {
      if (from === to) return
      const next = [...order]
      const fromIndex = next.indexOf(from)
      const toIndex = next.indexOf(to)
      if (fromIndex < 0 || toIndex < 0) return
      next.splice(fromIndex, 1)
      next.splice(toIndex, 0, from)
      onReorder(next)
    },
    [onReorder, order],
  )

  return (
    <div className={cn("space-y-4", className)}>
      {!compact ? (
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Page layout · drag panels to reorder
        </p>
      ) : null}
      {visibleOrder.map((blockId) => {
        const content = blocks[blockId]
        if (!content) return null
        return (
          <div
            key={blockId}
            draggable
            onDragStart={() => setDraggingId(blockId)}
            onDragEnd={() => {
              setDraggingId(null)
              setOverId(null)
            }}
            onDragOver={(event) => {
              event.preventDefault()
              if (draggingId && draggingId !== blockId) setOverId(blockId)
            }}
            onDragLeave={() => setOverId((current) => (current === blockId ? null : current))}
            onDrop={(event) => {
              event.preventDefault()
              if (draggingId) moveBlock(draggingId, blockId)
              setDraggingId(null)
              setOverId(null)
            }}
            className={cn(
              "group relative rounded-xl transition-shadow",
              draggingId === blockId && "opacity-60",
              overId === blockId && draggingId !== blockId && "ring-2 ring-primary/30",
            )}
          >
            <div
              className="absolute left-2 top-3 z-10 flex h-7 w-7 cursor-grab items-center justify-center rounded-md border border-border bg-background/90 text-muted-foreground opacity-100 sm:opacity-70 transition-opacity active:cursor-grabbing sm:group-hover:opacity-100 touch-none"
              aria-hidden
            >
              <GripVertical className="h-3.5 w-3.5" />
            </div>
            {content}
          </div>
        )
      })}
      {draggingId && onMoveBlockToColumn ? (
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setPeerDropActive(true)
          }}
          onDragLeave={() => setPeerDropActive(false)}
          onDrop={(event) => {
            event.preventDefault()
            if (draggingId) onMoveBlockToColumn(draggingId, peerColumn)
            setDraggingId(null)
            setOverId(null)
            setPeerDropActive(false)
          }}
          className={cn(
            "rounded-xl border border-dashed px-3 py-4 text-center text-xs text-muted-foreground transition-colors",
            peerDropActive
              ? "border-primary bg-primary/5 text-primary"
              : "border-border/80 bg-background/40",
          )}
        >
          {peerLabel}
        </div>
      ) : null}
    </div>
  )
}
