"use client"

import { Button } from "@/components/ui/button"
import { RADIUS, TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

/** No report-delivery backend exists yet, so every control here stays disabled with the reason. */
export const SCHEDULE_UNAVAILABLE_REASON =
  "Scheduled reports aren't available yet. Gravitre has no report delivery service to send them by email."

const DAYS = ["Monday", "Friday", "First of the month"] as const
const TIMES = ["8:00 AM", "12:00 PM", "5:00 PM"] as const

const SELECT =
  "h-11 min-w-0 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-60 sm:h-9"

export function ScheduledReportsPanel({ templateLabel }: { templateLabel: string }) {
  return (
    <section
      id="reports-scheduled"
      aria-labelledby="reports-scheduled-heading"
      className={cn(RADIUS.panel, "border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 sm:p-6")}
    >
      <h2 id="reports-scheduled-heading" className={cn(TYPE.cardTitle, "text-lg")}>
        Scheduled reports
      </h2>
      <div className={cn(RADIUS.card, "mt-4 bg-[color:var(--g-surface-2)] p-4 sm:p-5")}>
        <p className={TYPE.body}>
          Send me the <strong className="font-semibold">{templateLabel}</strong> report every
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label htmlFor="reports-schedule-day" className="sr-only">
            Day
          </label>
          <select id="reports-schedule-day" className={SELECT} disabled title={SCHEDULE_UNAVAILABLE_REASON} defaultValue={DAYS[0]}>
            {DAYS.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          <span className={TYPE.meta}>at</span>
          <label htmlFor="reports-schedule-time" className="sr-only">
            Time
          </label>
          <select id="reports-schedule-time" className={SELECT} disabled title={SCHEDULE_UNAVAILABLE_REASON} defaultValue={TIMES[0]}>
            {TIMES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <span className={TYPE.meta}>by email</span>
        </div>
        <Button variant="brand" size="sm" className="mt-4" disabled title={SCHEDULE_UNAVAILABLE_REASON}>
          Turn on
        </Button>
      </div>
    </section>
  )
}
