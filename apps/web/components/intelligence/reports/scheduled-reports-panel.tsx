"use client"

import { useEffect, useState, type Ref } from "react"
import useSWR from "swr"
import { toast } from "@/components/intelligence/overlays/toast"
import { Button } from "@/components/ui/button"
import {
  intelligenceReportsApi,
  type IntelligenceReportCadence,
  type IntelligenceReportTime,
} from "@/lib/api"
import { RADIUS, TYPE } from "@/lib/design-system"
import type { ReportTemplateId } from "@/lib/intelligence/saved-intelligence-views"
import { cn } from "@/lib/utils"

export const SCHEDULE_KEY = "intelligence/reports/schedule"

export const CADENCES: ReadonlyArray<{ id: IntelligenceReportCadence; label: string }> = [
  { id: "monday", label: "Monday" },
  { id: "friday", label: "Friday" },
  { id: "month_start", label: "First of the month" },
]

export const TIMES: ReadonlyArray<{ id: IntelligenceReportTime; label: string }> = [
  { id: "08:00", label: "8:00 AM" },
  { id: "12:00", label: "12:00 PM" },
  { id: "17:00", label: "5:00 PM" },
]

const SELECT =
  "h-11 min-w-0 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-60 sm:h-9"

const TEMPLATE_LABEL: Record<ReportTemplateId, string> = {
  business: "Business",
  agent: "Agent",
  prediction: "Prediction",
  governance: "Governance",
}

function formatSent(value: string | null | undefined): string | null {
  if (!value) return null
  const at = new Date(value)
  if (Number.isNaN(at.getTime())) return null
  return at.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

/**
 * Scheduled reports: one schedule per person. The backend emails the chosen
 * report on the cadence and local time (the organization's time zone), at
 * most once per slot, and records when it last went out or why it didn't.
 */
export function ScheduledReportsPanel({
  ref,
  enabled,
  templateId,
  templateLabel,
  periodDays,
}: {
  ref?: Ref<HTMLElement>
  enabled: boolean
  templateId: ReportTemplateId
  templateLabel: string
  periodDays: number
}) {
  const { data, error, isLoading, mutate } = useSWR(enabled ? SCHEDULE_KEY : null, () => intelligenceReportsApi.getSchedule(), {
    revalidateOnFocus: false,
  })
  const schedule = data?.schedule ?? null
  const [cadence, setCadence] = useState<IntelligenceReportCadence>("monday")
  const [time, setTime] = useState<IntelligenceReportTime>("08:00")
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (!schedule) return
    setCadence(schedule.cadence)
    setTime(schedule.time)
  }, [schedule])

  const on = Boolean(schedule?.enabled)
  // When a schedule is on, its own template is what gets sent; otherwise the one on screen.
  const scheduledTemplate = on && schedule ? schedule.templateId : templateId
  const label = on && schedule ? TEMPLATE_LABEL[schedule.templateId] : templateLabel
  const emailOff = data ? !data.emailEnabled : false
  const changed =
    on && schedule
      ? schedule.cadence !== cadence ||
        schedule.time !== time ||
        schedule.templateId !== templateId ||
        schedule.periodDays !== periodDays
      : false

  async function save(nextEnabled: boolean) {
    if (pending) return
    setPending(true)
    try {
      const next = await intelligenceReportsApi.putSchedule({
        templateId: nextEnabled ? templateId : scheduledTemplate,
        periodDays: nextEnabled ? periodDays : (schedule?.periodDays ?? periodDays),
        cadence,
        time,
        enabled: nextEnabled,
      })
      await mutate(next, { revalidate: false })
      const when = `${CADENCES.find((c) => c.id === cadence)?.label} at ${TIMES.find((t) => t.id === time)?.label}`
      if (nextEnabled) {
        toast.success(`${templateLabel} report scheduled`, { description: `Sent to you by email every ${when}.` })
      } else {
        toast.success("Scheduled report turned off")
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "The schedule was not saved.")
    } finally {
      setPending(false)
    }
  }

  const disabled = pending || isLoading || Boolean(error) || emailOff
  const lastSent = formatSent(schedule?.lastSentAt)

  return (
    <section
      ref={ref}
      id="reports-scheduled"
      aria-labelledby="reports-scheduled-heading"
      className={cn(RADIUS.panel, "scroll-mt-24 border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 sm:p-6")}
    >
      <h2 id="reports-scheduled-heading" className={cn(TYPE.cardTitle, "text-lg")}>
        Scheduled reports
      </h2>
      <div className={cn(RADIUS.card, "mt-4 bg-[color:var(--g-surface-2)] p-4 sm:p-5")}>
        <p className={TYPE.body}>
          Send me the <strong className="font-semibold">{label}</strong> report every
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label htmlFor="reports-schedule-day" className="sr-only">
            Day
          </label>
          <select
            id="reports-schedule-day"
            className={SELECT}
            disabled={disabled}
            value={cadence}
            onChange={(e) => setCadence(e.target.value as IntelligenceReportCadence)}
          >
            {CADENCES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <span className={TYPE.meta}>at</span>
          <label htmlFor="reports-schedule-time" className="sr-only">
            Time
          </label>
          <select
            id="reports-schedule-time"
            className={SELECT}
            disabled={disabled}
            value={time}
            onChange={(e) => setTime(e.target.value as IntelligenceReportTime)}
          >
            {TIMES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
          <span className={TYPE.meta}>by email</span>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {on ? (
            <>
              {changed ? (
                <Button variant="brand" size="sm" disabled={disabled} onClick={() => void save(true)}>
                  Save changes
                </Button>
              ) : null}
              <Button variant="outline" size="sm" disabled={pending} onClick={() => void save(false)}>
                Turn off
              </Button>
            </>
          ) : (
            <Button variant="brand" size="sm" disabled={disabled} onClick={() => void save(true)}>
              Turn on
            </Button>
          )}
        </div>
        {error ? (
          <p role="alert" className={cn(TYPE.meta, "mt-3")}>
            The schedule couldn&apos;t be loaded. Try again in a moment.
          </p>
        ) : emailOff ? (
          <p className={cn(TYPE.meta, "mt-3")}>Email delivery is turned off for Gravitre right now, so reports can&apos;t be scheduled.</p>
        ) : schedule?.lastError && on ? (
          <p role="alert" className={cn(TYPE.meta, "mt-3 text-[color:var(--g-danger,#a3333d)]")}>
            {schedule.lastError}
          </p>
        ) : on ? (
          <p className={cn(TYPE.meta, "mt-3")}>
            {lastSent ? `Last sent ${lastSent}. ` : ""}Times are in {schedule?.timezone ?? "UTC"}, your organization&apos;s time
            zone. Covers the last {schedule?.periodDays ?? periodDays} days.
          </p>
        ) : null}
      </div>
    </section>
  )
}
