"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { KIND_STYLES, type ScheduledItem, type ScheduleOccurrence } from "@/lib/schedules"
import { KindDot, isSameDay } from "./shared"

/** A contiguous run of days an item is scheduled, rendered as one bar. */
interface GanttSegment {
  /** Day offset (from rangeStart) the bar starts on. */
  startOffset: number
  /** Day offset (from rangeStart) the bar ends on (inclusive). */
  endOffset: number
  /** Number of individual occurrences inside this segment. */
  count: number
  /** Representative occurrence used for click/open handlers. */
  occurrence: ScheduleOccurrence
}

interface GanttRow {
  item: ScheduledItem
  segments: GanttSegment[]
}

const COL_WIDTH = 40 // px per day
const RAIL_WIDTH = 220 // px for the item label rail
const BAR_PAD = 3 // px inset inside a day cell

/** Whole-day offset of `date` from `start` (both truncated to midnight). */
function dayOffset(start: Date, date: Date): number {
  const a = new Date(start.getFullYear(), start.getMonth(), start.getDate()).getTime()
  const b = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  return Math.round((b - a) / 86_400_000)
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
  const reduceMotion = useReducedMotion()

  const days = useMemo(() => {
    const count = Math.round((rangeEnd.getTime() - rangeStart.getTime()) / 86_400_000) + 1
    return Array.from({ length: Math.max(count, 1) }, (_, i) => {
      const d = new Date(rangeStart)
      d.setDate(rangeStart.getDate() + i)
      return d
    })
  }, [rangeStart, rangeEnd])

  const rows = useMemo<GanttRow[]>(() => {
    const map = new Map<string, ScheduleOccurrence[]>()
    for (const occurrence of occurrences) {
      const list = map.get(occurrence.item.id)
      if (list) list.push(occurrence)
      else map.set(occurrence.item.id, [occurrence])
    }

    const built: GanttRow[] = []
    for (const list of map.values()) {
      // Collapse to one entry per day (keeping a count + earliest occurrence),
      // then merge consecutive days into spanning segments.
      const byOffset = new Map<number, { count: number; occurrence: ScheduleOccurrence }>()
      for (const occ of list) {
        const off = dayOffset(rangeStart, occ.date)
        if (off < 0 || off >= days.length) continue
        const existing = byOffset.get(off)
        if (existing) {
          existing.count += 1
          if (occ.date < existing.occurrence.date) existing.occurrence = occ
        } else {
          byOffset.set(off, { count: 1, occurrence: occ })
        }
      }

      const offsets = [...byOffset.keys()].sort((a, b) => a - b)
      const segments: GanttSegment[] = []
      for (const off of offsets) {
        const cell = byOffset.get(off)!
        const last = segments[segments.length - 1]
        if (last && off === last.endOffset + 1) {
          last.endOffset = off
          last.count += cell.count
        } else {
          segments.push({
            startOffset: off,
            endOffset: off,
            count: cell.count,
            occurrence: cell.occurrence,
          })
        }
      }

      if (segments.length > 0) built.push({ item: list[0].item, segments })
    }

    return built.sort((a, b) => {
      if (a.item.kind !== b.item.kind) return a.item.kind.localeCompare(b.item.kind)
      return a.item.title.localeCompare(b.item.title)
    })
  }, [occurrences, rangeStart, days.length])

  const today = new Date()
  const todayOffset = dayOffset(rangeStart, today)
  const showToday = todayOffset >= 0 && todayOffset < days.length

  if (rows.length === 0) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <div style={{ minWidth: RAIL_WIDTH + days.length * COL_WIDTH }}>
          {/* Header: day columns */}
          <div className="flex border-b border-border bg-muted/40">
            <div
              className="shrink-0 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              style={{ width: RAIL_WIDTH }}
            >
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
                  style={{ width: COL_WIDTH }}
                >
                  {day.getDate()}
                </div>
              ))}
            </div>
          </div>

          {/* Rows */}
          {rows.map((row, rowIndex) => {
            const style = KIND_STYLES[row.item.kind]
            return (
              <div key={row.item.id} className="flex border-b border-border last:border-b-0">
                <button
                  type="button"
                  onClick={() => onSelect(row.segments[0].occurrence)}
                  onDoubleClick={() => onOpen(row.segments[0].occurrence)}
                  className={cn(
                    "flex shrink-0 items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-muted/50",
                    row.item.id === selectedId && "bg-muted",
                  )}
                  style={{ width: RAIL_WIDTH }}
                >
                  <KindDot kind={row.item.kind} />
                  <span className="truncate text-sm font-medium text-foreground">
                    {row.item.title}
                  </span>
                </button>

                <div className="relative flex min-h-[44px] flex-1">
                  {/* Day grid background */}
                  {days.map((day, i) => (
                    <div
                      key={i}
                      className={cn(
                        "shrink-0 border-l border-border",
                        isSameDay(day, today) && "bg-primary/5",
                      )}
                      style={{ width: COL_WIDTH }}
                    />
                  ))}

                  {/* Today marker line */}
                  {showToday && (
                    <span
                      className="pointer-events-none absolute inset-y-0 z-10 w-px bg-primary/50"
                      style={{ left: todayOffset * COL_WIDTH + COL_WIDTH / 2 }}
                      aria-hidden
                    />
                  )}

                  {/* Spanning bars */}
                  {row.segments.map((segment, segIndex) => {
                    const span = segment.endOffset - segment.startOffset + 1
                    const left = segment.startOffset * COL_WIDTH + BAR_PAD
                    const width = span * COL_WIDTH - BAR_PAD * 2
                    const selected = row.item.id === selectedId
                    const showLabel = width >= 56 && segment.count > 1
                    const rangeText =
                      span > 1
                        ? `${segment.occurrence.date.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${days[segment.endOffset].toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
                        : segment.occurrence.date.toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                          })
                    return (
                      <motion.button
                        key={`${row.item.id}-${segment.startOffset}`}
                        type="button"
                        onClick={() => onSelect(segment.occurrence)}
                        onDoubleClick={() => onOpen(segment.occurrence)}
                        title={`${row.item.title} · ${rangeText} · ${segment.count} run${segment.count === 1 ? "" : "s"}`}
                        initial={reduceMotion ? false : { scaleX: 0, opacity: 0 }}
                        animate={{ scaleX: 1, opacity: 1 }}
                        transition={{
                          duration: 0.35,
                          delay: Math.min(rowIndex * 0.04 + segIndex * 0.015, 0.4),
                          ease: "easeOut",
                        }}
                        whileHover={{ scaleY: 1.12 }}
                        className={cn(
                          "absolute top-1/2 flex h-6 origin-left -translate-y-1/2 items-center overflow-hidden rounded-md px-2 shadow-sm transition-shadow hover:shadow-md",
                          selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                        )}
                        style={{ left, width, backgroundColor: style.color }}
                      >
                        {showLabel && (
                          <span className="truncate text-[10px] font-semibold text-white/95">
                            {segment.count} runs
                          </span>
                        )}
                      </motion.button>
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
