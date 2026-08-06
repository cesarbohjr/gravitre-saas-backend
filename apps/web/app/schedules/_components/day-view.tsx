"use client"

import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { kindColorVar, type ScheduleOccurrence } from "@/lib/schedules"
import { formatTime, isSameDay, scheduleBoardStyle } from "./shared"

const START_HOUR = 0
const END_HOUR = 24
const HOUR_PX = 56

/**
 * Single-day timeline — items placed by clock time on a fixed-height hour grid
 * so an empty day still shows the full 24h column.
 */
export function DayView({
  focusDate,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
}: {
  focusDate: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
}) {
  const hours = useMemo(
    () => Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i),
    [],
  )
  const dayOccurrences = useMemo(
    () =>
      occurrences
        .filter((o) => isSameDay(o.date, focusDate))
        .sort((a, b) => a.date.getTime() - b.date.getTime()),
    [occurrences, focusDate],
  )
  const gridHeight = hours.length * HOUR_PX
  const today = new Date()
  const isToday = isSameDay(focusDate, today)
  const nowTop =
    isToday
      ? ((today.getHours() - START_HOUR) * 60 + today.getMinutes()) * (HOUR_PX / 60)
      : null

  return (
    <div
      className="flex w-full min-w-0 flex-col overflow-hidden rounded-2xl border border-border bg-card"
      style={scheduleBoardStyle}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {focusDate.toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          </p>
          <p className="text-xs text-muted-foreground">
            {dayOccurrences.length === 0
              ? "No items scheduled — full day timeline kept open"
              : `${dayOccurrences.length} item${dayOccurrences.length === 1 ? "" : "s"}`}
          </p>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="relative flex" style={{ minHeight: gridHeight, height: gridHeight }}>
          {/* Time gutter */}
          <div className="w-16 shrink-0 border-r border-border bg-muted/20">
            {hours.map((hour) => (
              <div
                key={hour}
                className="border-b border-border/50 px-2 text-right text-[10px] font-medium tabular-nums text-muted-foreground"
                style={{ height: HOUR_PX }}
              >
                <span className="-translate-y-1.5 inline-block">
                  {new Date(2000, 0, 1, hour).toLocaleTimeString(undefined, {
                    hour: "numeric",
                  })}
                </span>
              </div>
            ))}
          </div>

          {/* Event lane — clip so stacked cards never spill past the board edge */}
          <div className="relative min-w-0 flex-1 overflow-hidden">
            {hours.map((hour) => (
              <div
                key={hour}
                className="border-b border-border/40"
                style={{ height: HOUR_PX }}
              />
            ))}

            {nowTop != null && nowTop >= 0 && nowTop <= gridHeight ? (
              <div
                className="pointer-events-none absolute right-0 left-0 z-20 border-t-2 border-destructive"
                style={{ top: nowTop }}
              >
                <span className="absolute -top-2 left-2 rounded bg-destructive px-1 text-[9px] font-semibold text-destructive-foreground">
                  Now
                </span>
              </div>
            ) : null}

            {dayOccurrences.map((occurrence, index) => {
              const minutes =
                (occurrence.date.getHours() - START_HOUR) * 60 + occurrence.date.getMinutes()
              const top = Math.max(0, minutes * (HOUR_PX / 60))
              const color = kindColorVar(occurrence.item.kind)
              const selected = occurrence.item.id === selectedId
              // Equal lanes stay fully inside the column (old 28%+68% math overflowed).
              const laneCount = 3
              const lane = index % laneCount
              return (
                <button
                  key={occurrence.key}
                  type="button"
                  onFocus={() => onSelect(occurrence)}
                  onClick={() => onOpen(occurrence)}
                  className={cn(
                    "absolute z-10 flex min-h-[2.5rem] flex-col justify-center overflow-hidden rounded-lg px-2.5 py-1.5 text-left shadow-sm transition-shadow hover:shadow-md",
                    selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                  )}
                  style={{
                    top,
                    left: `calc(0.5rem + ${lane} * ((100% - 1rem) / ${laneCount}))`,
                    width: `calc((100% - 1rem) / ${laneCount} - 0.25rem)`,
                    backgroundColor: `color-mix(in oklab, ${color} 18%, white)`,
                    borderLeft: `3px solid ${color}`,
                  }}
                  title={`${occurrence.item.title} · ${formatTime(occurrence.date)}`}
                >
                  <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">
                    {formatTime(occurrence.date)}
                  </span>
                  <span className="truncate text-xs font-medium text-foreground">
                    {occurrence.item.title}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
