"use client"

import { useEffect, useMemo, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { ChevronLeft, ChevronRight, CalendarClock, Repeat, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { StatusBadge } from "@/components/gravitre/status-badge"
import {
  KIND_STYLES,
  kindColorVar,
  type ScheduleOccurrence,
} from "@/lib/schedules"
import {
  addDays,
  formatTime,
  isSameDay,
  startOfMonth,
  startOfWeek,
  statusLabel,
  statusVariant,
} from "./shared"

const WEEKDAY_INITIALS = ["M", "T", "W", "T", "F", "S", "S"]

/**
 * Phone-first schedule surface.
 *
 * A 7-column month grid is unusable at 375px — day cells collapse to ~48px and
 * event chips become unreadable, which is why the desktop grid used to force a
 * horizontal scroll. Instead, mobile gets the pattern every native calendar
 * app uses: a compact week strip for date selection plus a vertical agenda
 * timeline for the selected day.
 */
export function MobileAgenda({
  month,
  occurrences,
  onOpen,
  onMonthChange,
}: {
  month: Date
  occurrences: ScheduleOccurrence[]
  onOpen: (occurrence: ScheduleOccurrence) => void
  onMonthChange: (month: Date) => void
}) {
  const reduceMotion = useReducedMotion()
  const today = useMemo(() => new Date(), [])
  const [selectedDate, setSelectedDate] = useState<Date>(() =>
    today.getMonth() === month.getMonth() && today.getFullYear() === month.getFullYear()
      ? today
      : startOfMonth(month),
  )

  // Keep the strip inside the month the toolbar is showing when the user pages
  // months from the header rather than the strip arrows.
  useEffect(() => {
    setSelectedDate((current) => {
      if (
        current.getMonth() === month.getMonth() &&
        current.getFullYear() === month.getFullYear()
      ) {
        return current
      }
      return today.getMonth() === month.getMonth() && today.getFullYear() === month.getFullYear()
        ? today
        : startOfMonth(month)
    })
  }, [month, today])

  const weekStart = useMemo(() => startOfWeek(selectedDate), [selectedDate])
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  )

  const goToWeek = (delta: number) => {
    const next = addDays(selectedDate, delta * 7)
    setSelectedDate(next)
    if (next.getMonth() !== month.getMonth() || next.getFullYear() !== month.getFullYear()) {
      onMonthChange(startOfMonth(next))
    }
  }

  const dayOccurrences = useMemo(
    () =>
      occurrences
        .filter((o) => isSameDay(o.date, selectedDate))
        .sort((a, b) => a.date.getTime() - b.date.getTime()),
    [occurrences, selectedDate],
  )

  const weekLabel = `${weekStart.toLocaleString(undefined, { month: "short", day: "numeric" })} – ${addDays(
    weekStart,
    6,
  ).toLocaleString(undefined, { month: "short", day: "numeric" })}`

  return (
    <div className="space-y-4">
      {/* Week strip */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Week of
            </p>
            <p className="truncate text-base font-semibold text-foreground">{weekLabel}</p>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => goToWeek(-1)}
              aria-label="Previous week"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors active:bg-muted"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={() => goToWeek(1)}
              aria-label="Next week"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors active:bg-muted"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-7 gap-1">
          {weekDays.map((day, idx) => {
            const selected = isSameDay(day, selectedDate)
            const isToday = isSameDay(day, today)
            const kinds = new Set(
              occurrences.filter((o) => isSameDay(o.date, day)).map((o) => o.item.kind),
            )
            return (
              <button
                key={day.toISOString()}
                type="button"
                onClick={() => setSelectedDate(day)}
                aria-pressed={selected}
                aria-label={day.toLocaleDateString(undefined, {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                })}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-2xl px-0.5 py-2 transition-colors",
                  selected ? "bg-primary text-primary-foreground" : "active:bg-muted",
                )}
              >
                <span
                  className={cn(
                    "text-[11px] font-medium uppercase",
                    selected ? "text-primary-foreground/80" : "text-muted-foreground",
                  )}
                >
                  {WEEKDAY_INITIALS[idx]}
                </span>
                <span
                  className={cn(
                    "text-base font-semibold tabular-nums",
                    selected
                      ? "text-primary-foreground"
                      : isToday
                        ? "text-primary"
                        : day.getMonth() === month.getMonth()
                          ? "text-foreground"
                          : "text-muted-foreground/50",
                  )}
                >
                  {day.getDate()}
                </span>
                <span className="flex h-1.5 items-center gap-0.5">
                  {[...kinds].slice(0, 3).map((kind) => (
                    <span
                      key={kind}
                      className="h-1.5 w-1.5 rounded-full"
                      style={{
                        backgroundColor: selected
                          ? "currentColor"
                          : kindColorVar(kind),
                      }}
                    />
                  ))}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Agenda timeline for the selected day */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">
            {isSameDay(selectedDate, today)
              ? "Today"
              : selectedDate.toLocaleDateString(undefined, { weekday: "long" })}
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              {selectedDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            </span>
          </h2>
          <span className="shrink-0 text-xs text-muted-foreground">
            {dayOccurrences.length} {dayOccurrences.length === 1 ? "item" : "items"}
          </span>
        </div>

        {dayOccurrences.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border py-10 text-center">
            <CalendarClock className="h-6 w-6 text-muted-foreground/60" />
            <p className="text-sm text-muted-foreground">Nothing scheduled this day.</p>
          </div>
        ) : (
          <ol className="relative space-y-3">
            {/* Timeline rail */}
            <span
              className="absolute left-[3.75rem] top-2 bottom-2 w-px bg-border"
              aria-hidden
            />
            {dayOccurrences.map((occurrence, index) => {
              const color = kindColorVar(occurrence.item.kind)
              const past = occurrence.date.getTime() < today.getTime()
              return (
                <motion.li
                  key={occurrence.key}
                  initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: 0.24,
                    delay: Math.min(index * 0.04, 0.3),
                    ease: "easeOut",
                  }}
                  className="relative flex items-start gap-3"
                >
                  <span
                    className={cn(
                      "w-12 shrink-0 pt-2.5 text-right text-xs font-semibold tabular-nums",
                      past ? "text-muted-foreground/60" : "text-foreground",
                    )}
                  >
                    {formatTime(occurrence.date)}
                  </span>
                  {/* Marker */}
                  <span className="relative z-10 mt-3 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-card">
                    <span
                      className="h-3.5 w-3.5 rounded-full border-2"
                      style={{
                        borderColor: color,
                        backgroundColor: past
                          ? "transparent"
                          : `color-mix(in oklab, ${color} 45%, transparent)`,
                      }}
                    />
                  </span>
                  <button
                    type="button"
                    onClick={() => onOpen(occurrence)}
                    className="min-w-0 flex-1 rounded-xl border border-border/70 p-3 text-left transition-colors active:bg-muted/60"
                    style={{
                      backgroundColor: `color-mix(in oklab, ${color} 8%, transparent)`,
                      borderLeftColor: color,
                      borderLeftWidth: 3,
                    }}
                  >
                    <p className="truncate text-sm font-semibold text-foreground">
                      {occurrence.item.title}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1" style={{ color }}>
                        <span
                          className="h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        {KIND_STYLES[occurrence.item.kind].label}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTime(occurrence.date)}
                      </span>
                      {occurrence.projected && (
                        <span className="inline-flex items-center gap-1">
                          <Repeat className="h-3 w-3" />
                          Projected
                        </span>
                      )}
                    </div>
                    {occurrence.item.subtitle && (
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {occurrence.item.subtitle}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-2">
                      <StatusBadge variant={statusVariant(occurrence.item.status)} dot>
                        {statusLabel(occurrence.item.status)}
                      </StatusBadge>
                      {occurrence.item.isSample && (
                        <StatusBadge variant="muted">Sample</StatusBadge>
                      )}
                    </div>
                  </button>
                </motion.li>
              )
            })}
          </ol>
        )}
      </div>
    </div>
  )
}
