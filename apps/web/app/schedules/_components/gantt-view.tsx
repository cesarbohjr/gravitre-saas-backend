"use client"

import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { KIND_STYLES, type ScheduledItem, type ScheduleOccurrence } from "@/lib/schedules"
import { KindDot, isSameDay } from "./shared"

interface GanttRow {
  item: ScheduledItem
  occurrences: ScheduleOccurrence[]
}

export function GanttView({
  rangeStart,
  rangeEnd,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
}: {
  rangeStart: Date
  rangeEnd: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
}) {
  const days = useMemo(() => {
    const count =
      Math.round((rangeEnd.getTime() - rangeStart.getTime()) / 86_400_000) + 1
    return Array.from({ length: Math.max(count, 1) }, (_, i) => {
      const d = new Date(rangeStart)
      d.setDate(rangeStart.getDate() + i)
      return d
    })
  }, [rangeStart, rangeEnd])

  const rows = useMemo<GanttRow[]>(() => {
    const map = new Map<string, GanttRow>()
    for (const occurrence of occurrences) {
      const existing = map.get(occurrence.item.id)
      if (existing) existing.occurrences.push(occurrence)
      else map.set(occurrence.item.id, { item: occurrence.item, occurrences: [occurrence] })
    }
    return Array.from(map.values()).sort((a, b) => {
      if (a.item.kind !== b.item.kind) return a.item.kind.localeCompare(b.item.kind)
      return a.item.title.localeCompare(b.item.title)
    })
  }, [occurrences])

  const today = new Date()
  const colWidth = 40 // px per day

  if (rows.length === 0) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <div style={{ minWidth: 220 + days.length * colWidth }}>
          {/* Header: day columns */}
          <div className="flex border-b border-border bg-muted/40">
            <div className="w-[220px] shrink-0 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Item
            </div>
            <div className="flex">
              {days.map((day, i) => (
                <div
                  key={i}
                  className={cn(
                    "shrink-0 border-l border-border py-2 text-center text-[10px] text-muted-foreground",
                    isSameDay(day, today) && "bg-primary/10 font-semibold text-primary",
                  )}
                  style={{ width: colWidth }}
                >
                  {day.getDate()}
                </div>
              ))}
            </div>
          </div>

          {/* Rows */}
          {rows.map((row) => {
            const style = KIND_STYLES[row.item.kind]
            return (
              <div key={row.item.id} className="flex border-b border-border last:border-b-0">
                <button
                  type="button"
                  onClick={() => onSelect(row.occurrences[0])}
                  onDoubleClick={() => onOpen(row.occurrences[0])}
                  className={cn(
                    "flex w-[220px] shrink-0 items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-muted/50",
                    row.item.id === selectedId && "bg-muted",
                  )}
                >
                  <KindDot kind={row.item.kind} />
                  <span className="truncate text-sm font-medium text-foreground">
                    {row.item.title}
                  </span>
                </button>
                <div className="relative flex">
                  {days.map((day, i) => (
                    <div
                      key={i}
                      className={cn(
                        "shrink-0 border-l border-border",
                        isSameDay(day, today) && "bg-primary/5",
                      )}
                      style={{ width: colWidth }}
                    />
                  ))}
                  {/* Occurrence markers */}
                  {row.occurrences.map((occurrence) => {
                    const offset = Math.round(
                      (new Date(
                        occurrence.date.getFullYear(),
                        occurrence.date.getMonth(),
                        occurrence.date.getDate(),
                      ).getTime() -
                        new Date(
                          rangeStart.getFullYear(),
                          rangeStart.getMonth(),
                          rangeStart.getDate(),
                        ).getTime()) /
                        86_400_000,
                    )
                    if (offset < 0 || offset >= days.length) return null
                    const selected = occurrence.item.id === selectedId
                    return (
                      <button
                        key={occurrence.key}
                        type="button"
                        onClick={() => onSelect(occurrence)}
                        onDoubleClick={() => onOpen(occurrence)}
                        title={`${occurrence.item.title} · ${occurrence.date.toLocaleString()}`}
                        className={cn(
                          "absolute top-1/2 h-5 -translate-y-1/2 rounded-md transition-all hover:brightness-110",
                          selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                        )}
                        style={{
                          left: offset * colWidth + 6,
                          width: colWidth - 12,
                          backgroundColor: style.color,
                        }}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
