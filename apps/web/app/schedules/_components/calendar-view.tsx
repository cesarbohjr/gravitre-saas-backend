"use client"

import { useMemo, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { kindColorVar, type ScheduleOccurrence } from "@/lib/schedules"
import {
  addDays,
  formatTime,
  isSameDay,
  scheduleBoardStyle,
  startOfCalendarGrid,
} from "./shared"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
/** Always 6 weeks × 7 days so the grid never changes height with content or month length. */
const GRID_DAYS = 42
/** Chips that fit a comfort-density cell before collapsing into "+N more". */
const MAX_CHIPS = 3

/**
 * Desktop month grid.
 *
 * Rendered as a ruled grid (hairline gaps over a border-tone board) so the
 * month reads as one instrument; each cell is still a droppable surface and weekends /
 * out-of-month days can recede without extra borders. Phones get
 * `MobileAgenda` instead — see that file for why.
 */
export function CalendarView({
  month,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
  onMoveRequest,
}: {
  month: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
  onMoveRequest?: (occurrence: ScheduleOccurrence, targetDate: Date) => void
}) {
  const reduceMotion = useReducedMotion()
  const [draggingKey, setDraggingKey] = useState<string | null>(null)
  const [dropDayKey, setDropDayKey] = useState<string | null>(null)
  const gridStart = useMemo(() => startOfCalendarGrid(month), [month])
  const days = useMemo(
    () => Array.from({ length: GRID_DAYS }, (_, i) => addDays(gridStart, i)),
    [gridStart],
  )
  const today = new Date()

  return (
    <div
      className="flex w-full min-w-0 flex-col overflow-hidden border border-[color:var(--g-border-default)] bg-background"
      style={scheduleBoardStyle}
    >
      <div className="grid shrink-0 grid-cols-7 border-b border-[color:var(--g-border-default)]">
        {WEEKDAYS.map((day, idx) => (
          <div
            key={day}
            className={cn(
              "px-2 py-1.5 text-left text-xs font-medium",
              idx > 4 ? "text-muted-foreground" : "text-foreground",
            )}
          >
            {day}
          </div>
        ))}
      </div>

      {/* Fixed 6×7 board — empty months keep the same footprint as busy ones. */}
      <div
        className="grid min-h-0 flex-1 grid-cols-7 gap-px bg-[color:var(--g-border-subtle)]"
        style={{ gridTemplateRows: "repeat(6, minmax(0, 1fr))" }}
      >
        {days.map((day, idx) => {
          const inMonth = day.getMonth() === month.getMonth()
          const isWeekend = idx % 7 > 4
          const dayOccurrences = occurrences.filter((o) => isSameDay(o.date, day))
          const isToday = isSameDay(day, today)
          const isDropTarget = dropDayKey === String(idx)
          return (
            <div
              key={idx}
              onDragOver={(event) => {
                if (!draggingKey || !onMoveRequest) return
                event.preventDefault()
                setDropDayKey(String(idx))
              }}
              onDragLeave={() =>
                setDropDayKey((current) => (current === String(idx) ? null : current))
              }
              onDrop={(event) => {
                event.preventDefault()
                if (!draggingKey || !onMoveRequest) return
                const occurrence = occurrences.find((entry) => entry.key === draggingKey)
                if (!occurrence) return
                const nextDate = new Date(day)
                nextDate.setHours(
                  occurrence.date.getHours(),
                  occurrence.date.getMinutes(),
                  occurrence.date.getSeconds(),
                  0,
                )
                onMoveRequest(occurrence, nextDate)
                setDraggingKey(null)
                setDropDayKey(null)
              }}
              className={cn(
                "flex h-full min-h-0 flex-col overflow-hidden p-1.5 transition-colors",
                inMonth
                  ? isWeekend
                    ? "bg-[color:var(--g-rail-bg)]"
                    : "bg-background"
                  : "bg-[color:var(--g-rail-bg)]",
                isToday && "shadow-[inset_0_2px_0_var(--g-text-primary)]",
                isDropTarget && "bg-[color:var(--g-brand)]/5 shadow-[inset_0_0_0_2px_var(--g-brand)]",
              )}
            >
              <div className="mb-1.5 flex shrink-0 items-center justify-between">
                <span
                  className={cn(
                    "inline-flex h-6 min-w-6 items-center justify-center rounded-[3px] px-1 text-[13px] tabular-nums",
                    isToday
                      ? "bg-[color:var(--g-text-primary)] font-semibold text-background"
                      : inMonth
                        ? "font-medium text-foreground"
                        : "text-muted-foreground/50",
                  )}
                >
                  {day.getDate()}
                </span>
                {dayOccurrences.length > 0 && (
                  <span className="pr-0.5 text-[11px] font-medium tabular-nums text-muted-foreground">
                    {dayOccurrences.length}
                  </span>
                )}
              </div>

              <div className="min-h-0 flex-1 space-y-1 overflow-hidden">
                {dayOccurrences.slice(0, MAX_CHIPS).map((occurrence, chipIdx) => {
                  const color = kindColorVar(occurrence.item.kind)
                  const selected = occurrence.item.id === selectedId
                  const draggable = Boolean(onMoveRequest) && !occurrence.item.isSample
                  return (
                    <motion.button
                      key={occurrence.key}
                      type="button"
                      draggable={draggable}
                      onDragStart={() => setDraggingKey(occurrence.key)}
                      onDragEnd={() => {
                        setDraggingKey(null)
                        setDropDayKey(null)
                      }}
                      onFocus={() => onSelect(occurrence)}
                      onClick={() => onOpen(occurrence)}
                      title={`${occurrence.item.title} · click to reschedule or edit`}
                      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        duration: 0.2,
                        delay: Math.min(idx * 0.004 + chipIdx * 0.03, 0.25),
                        ease: "easeOut",
                      }}
                      whileTap={{ scale: 0.98 }}
                      className={cn(
                        "flex w-full items-center gap-1.5 rounded-[3px] px-1.5 py-1 text-left text-xs",
                        selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                        draggable && "cursor-grab active:cursor-grabbing",
                        draggingKey === occurrence.key && "opacity-60",
                        !inMonth && "opacity-60",
                      )}
                      style={{
                        backgroundColor: `color-mix(in oklab, ${color} 9%, transparent)`,
                        borderLeft: `2px solid ${color}`,
                      }}
                    >
                      <span className="truncate font-medium text-foreground">
                        {occurrence.item.title}
                      </span>
                      <span className="ml-auto shrink-0 text-[10px] tabular-nums text-muted-foreground">
                        {formatTime(occurrence.date)}
                      </span>
                    </motion.button>
                  )
                })}

                {dayOccurrences.length > MAX_CHIPS && (
                  <button
                    type="button"
                    onClick={() => onOpen(dayOccurrences[MAX_CHIPS])}
                    className="w-full rounded-[3px] px-1.5 py-0.5 text-left text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    +{dayOccurrences.length - MAX_CHIPS} more
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
