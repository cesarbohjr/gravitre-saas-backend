"use client"

import Link from "next/link"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { Button } from "@/components/ui/button"
import {
  confidenceLabel,
  formatPct,
  type Forecast,
} from "@/components/intelligence/forecasts/forecast-model"
import {
  forecastDotColor,
  KIND_CHIP_CLASS,
  KIND_LABEL,
} from "@/components/intelligence/forecasts/forecast-tone"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight, Sparkle } from "@phosphor-icons/react"

const SECTION_LABEL = "font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]"

export type ForecastOutcome = "happened" | "didnt"

export function ForecastDetail({
  forecast,
  rejecting,
  rejected,
  onReject,
}: {
  forecast: Forecast
  rejecting: boolean
  rejected: boolean
  onReject: () => void
}) {
  const { summonWorkspace } = useGravitreAIWorkspace()
  const pct = forecast.confidence == null ? null : Math.round(forecast.confidence * 100)
  const kindLower = KIND_LABEL[forecast.kind].toLowerCase()
  const color = forecastDotColor(forecast)

  return (
    <article
      aria-labelledby="forecast-detail-heading"
      className="flex flex-col gap-5 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)] sm:p-6"
    >
      <div className="flex flex-wrap gap-2">
        <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", KIND_CHIP_CLASS[forecast.kind])}>
          {KIND_LABEL[forecast.kind]}
        </span>
        {forecast.area ? (
          <span className="rounded-full bg-[color:var(--g-surface-2)] px-2.5 py-1 text-xs text-foreground">
            {forecast.area}
          </span>
        ) : null}
        <span className="rounded-full bg-[color:var(--g-surface-2)] px-2.5 py-1 text-xs text-foreground">
          {forecast.whenLabel}
        </span>
      </div>

      <div>
        <h2 id="forecast-detail-heading" className="text-xl font-semibold tracking-[-0.015em] text-foreground sm:text-2xl">
          {forecast.title}
        </h2>
        {forecast.summary ? <p className={cn(TYPE.body, "mt-2 text-pretty")}>{forecast.summary}</p> : null}
      </div>

      <div className="rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-4 py-3.5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-muted-foreground">Confidence</span>
          <span className="text-sm font-semibold text-foreground tabular-nums">
            {confidenceLabel(forecast.confidence)}
            {pct != null ? ` · ${pct}%` : ""}
          </span>
        </div>
        <div
          role="meter"
          aria-label="Confidence"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct ?? undefined}
          aria-valuetext={pct == null ? "Not scored" : `${pct} percent`}
          className="relative mt-2.5 h-1.5 rounded-full bg-[color:var(--g-border-subtle)]"
        >
          {pct != null ? (
            <>
              <div
                className="absolute inset-y-0 left-0 rounded-full opacity-30"
                style={{ width: `${pct}%`, background: color }}
              />
              <div
                className="absolute top-1/2 h-3.5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{ left: `${pct}%`, background: color }}
              />
            </>
          ) : null}
        </div>
        <p className={cn(TYPE.meta, "mt-2")}>{forecast.confidenceNote}</p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <p className={SECTION_LABEL}>Why Gravitre thinks so</p>
          {forecast.drivers.length > 0 ? (
            <ul className="mt-2 space-y-1.5">
              {forecast.drivers.map((driver) => (
                <li key={driver} className="flex items-start gap-2 text-sm text-foreground">
                  <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
                  {driver}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground" title="No drivers recorded by the source">
              —
            </p>
          )}
        </div>
        <div>
          <p className={SECTION_LABEL}>Evidence</p>
          {forecast.evidence.length > 0 ? (
            <div className="mt-2 space-y-1.5 rounded-[var(--np-radius-md)] border border-divide px-3 py-2.5 text-sm text-foreground">
              {forecast.evidence.map((line) => (
                <p key={line} className="text-pretty">
                  {line}
                </p>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground" title="No evidence attached yet">
              —
            </p>
          )}
          <Link
            href={forecast.evidenceHref}
            className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-[color:var(--g-brand-active)] underline underline-offset-2 hover:text-[color:var(--g-brand-hover)] dark:text-[color:var(--g-brand)]"
          >
            See the full evidence trail
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-divide pt-4">
        {forecast.action.type === "link" ? (
          <Button variant="brand" asChild>
            <Link href={forecast.action.href}>
              <Sparkle className="mr-1.5 h-4 w-4" weight="fill" aria-hidden />
              {forecast.action.label}
            </Link>
          </Button>
        ) : (
          <Button
            variant="brand"
            onClick={() => {
              if (forecast.action.type !== "ask") return
              summonWorkspace({
                presentation: "compact",
                agentScope: null,
                composerText: forecast.action.prompt,
                submit: false,
              })
            }}
          >
            <Sparkle className="mr-1.5 h-4 w-4" weight="fill" aria-hidden />
            <span className="max-w-[22rem] truncate">{forecast.action.label}</span>
          </Button>
        )}
        <Button
          variant="outline"
          disabled
          title="Snoozing forecasts isn't available yet. Gravitre has no snooze for forecasts on the server."
        >
          Snooze
        </Button>
        <span className="flex-1" />
        <Button
          variant="ghost"
          className="text-muted-foreground"
          disabled={rejecting || rejected}
          onClick={onReject}
        >
          {rejected ? `Marked not a real ${kindLower}` : rejecting ? "Saving…" : `Not a real ${kindLower}`}
        </Button>
      </div>
    </article>
  )
}

export function ForecastList({
  forecasts,
  selectedKey,
  onSelect,
}: {
  forecasts: Forecast[]
  selectedKey: string | null
  onSelect: (key: string) => void
}) {
  return (
    <section
      aria-labelledby="forecast-list-heading"
      className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]"
    >
      <h2 id="forecast-list-heading" className={TYPE.cardTitle}>
        All forecasts
      </h2>
      {forecasts.length === 0 ? (
        <p className={cn(TYPE.meta, "mt-3")}>No forecasts for this department.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {forecasts.map((forecast) => {
            const on = forecast.key === selectedKey
            return (
              <li key={forecast.key}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => onSelect(forecast.key)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-[var(--np-radius-md)] border px-3.5 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    on
                      ? "border-foreground bg-[color:var(--g-surface-2)]"
                      : "border-divide hover:border-foreground",
                  )}
                >
                  <span
                    aria-hidden
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: forecastDotColor(forecast) }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">{forecast.title}</span>
                    <span className={cn(TYPE.meta, "block truncate")}>
                      {forecast.whenLabel}
                      {forecast.area ? ` · ${forecast.area}` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-foreground">{formatPct(forecast.confidence)}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export function ForecastOutcomeCard({
  forecast,
  recorded,
  saving,
  onRecord,
}: {
  forecast: Forecast | null
  recorded: ForecastOutcome | undefined
  saving: boolean
  onRecord: (outcome: ForecastOutcome) => void
}) {
  const disabled = !forecast || saving || Boolean(recorded)
  return (
    <section
      aria-labelledby="forecast-outcome-heading"
      className="rounded-[var(--np-radius-lg)] bg-foreground p-5 text-background shadow-[var(--np-shadow)]"
    >
      <h2 id="forecast-outcome-heading" className="flex items-center gap-2 text-base font-semibold">
        <Sparkle className="h-4 w-4 text-[color:var(--g-brand)]" weight="fill" aria-hidden />
        Did it happen?
      </h2>
      <p className="mt-2 text-sm text-background/75">
        Telling Gravitre how a forecast turned out is the fastest way to make the next one sharper.
      </p>
      {forecast ? (
        <p className="mt-2 truncate text-xs text-background/60">For: {forecast.title}</p>
      ) : null}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={disabled}
          aria-pressed={recorded === "happened"}
          onClick={() => onRecord("happened")}
          className="min-h-10 rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-active)] px-3 text-sm font-medium text-white transition-colors hover:bg-[color:var(--g-brand-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          It happened
        </button>
        <button
          type="button"
          disabled={disabled}
          aria-pressed={recorded === "didnt"}
          onClick={() => onRecord("didnt")}
          className="min-h-10 rounded-[var(--np-radius-md)] border border-background/25 px-3 text-sm font-medium text-background transition-colors hover:bg-background/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          It didn&apos;t
        </button>
      </div>
      {recorded ? (
        <p role="status" className="mt-3 text-xs text-background/75">
          Recorded: {recorded === "happened" ? "it happened" : "it didn't happen"}.
        </p>
      ) : null}
    </section>
  )
}
