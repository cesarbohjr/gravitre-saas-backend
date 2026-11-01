"use client"

import Link from "next/link"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
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
import { INTEL } from "@/components/intelligence/shell/intel-ui"
import type { ForecastSnooze } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight, ShareNetwork, Sparkle } from "@phosphor-icons/react"

const SECTION_LABEL = INTEL.monoLabel
const CHIP = "rounded-full bg-[color:var(--g-background-muted)] px-2.5 py-1 text-xs text-[#33342f] dark:text-[color:var(--g-text-primary)]"
const BUTTON_OUTLINE =
  "inline-flex min-h-[42px] items-center gap-1.5 rounded-[10px] border border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)] px-3.5 text-sm text-[color:var(--g-text-primary)] transition-colors hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
const BUTTON_BRAND =
  "inline-flex min-h-10 items-center gap-2 rounded-[10px] bg-[color:var(--g-emerald)] px-4 text-sm font-medium text-white transition-colors hover:bg-[color:var(--g-emerald-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"

export type ForecastOutcome = "happened" | "didnt"

export function ForecastDetail({
  forecast,
  rejecting,
  rejected,
  onReject,
  snoozing = false,
  onSnooze,
  onShare,
}: {
  forecast: Forecast
  rejecting: boolean
  rejected: boolean
  onReject: () => void
  snoozing?: boolean
  /** Hides this forecast for the whole team for a week. */
  onSnooze?: () => void
  /** Opens "Share this finding" for this forecast. */
  onShare?: () => void
}) {
  const { summonWorkspace } = useGravitreAIWorkspace()
  const pct = forecast.confidence == null ? null : Math.round(forecast.confidence * 100)
  const kindLower = KIND_LABEL[forecast.kind].toLowerCase()
  const color = forecastDotColor(forecast)

  return (
    <article
      aria-labelledby="forecast-detail-heading"
      className="flex flex-col gap-[18px] rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-5 sm:p-6"
    >
      <div className="flex flex-wrap gap-2">
        <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", KIND_CHIP_CLASS[forecast.kind])}>
          {KIND_LABEL[forecast.kind]}
        </span>
        {forecast.area ? (
          <span className={CHIP}>
            {forecast.area}
          </span>
        ) : null}
        <span className={CHIP}>
          {forecast.whenLabel}
        </span>
      </div>

      <div className="flex flex-col gap-1.5">
        <h2 id="forecast-detail-heading" className="text-xl font-semibold tracking-[-0.015em] text-foreground sm:text-2xl">
          {forecast.title}
        </h2>
        {forecast.summary ? <p className="text-pretty text-[15px] leading-normal text-[#33342f] dark:text-[color:var(--g-text-secondary)]">{forecast.summary}</p> : null}
      </div>

      <div className="flex flex-col gap-2 rounded-[14px] bg-[color:var(--g-surface-2)] p-4">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[13px] text-[color:var(--g-text-secondary)]">Confidence</span>
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
          className="relative h-2.5 rounded-full bg-[#e9e9e3] dark:bg-[color:var(--g-border-subtle)]"
        >
          {pct != null ? (
            <>
              <div
                className="absolute inset-y-0 left-0 rounded-full opacity-25"
                style={{ width: `${pct}%`, background: color }}
              />
              <div
                className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-sm"
                style={{ left: `${pct}%`, background: color }}
              />
            </>
          ) : null}
        </div>
        <p className="text-xs leading-[1.45] text-[color:var(--g-text-secondary)]">{forecast.confidenceNote}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className={SECTION_LABEL}>Why Gravitre thinks so</p>
          {forecast.drivers.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {forecast.drivers.map((driver) => (
                <li key={driver} className="flex items-start gap-2 text-[13.5px] leading-[1.45] text-foreground">
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
            <div className="mt-2 space-y-1.5 rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2.5 text-[13px] leading-normal text-[#33342f] dark:text-[color:var(--g-text-secondary)]">
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
            className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-[color:var(--g-brand-active)] underline underline-offset-2 hover:text-[color:var(--g-brand-hover)] dark:text-[color:var(--g-brand)]"
          >
            See the full evidence trail
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 border-t border-[color:var(--g-background-muted)] pt-4">
        {forecast.action.type === "link" ? (
          <Link href={forecast.action.href} className={BUTTON_BRAND}>
            <Sparkle className="h-[15px] w-[15px]" weight="fill" aria-hidden />
            {forecast.action.label}
          </Link>
        ) : (
          <button
            type="button"
            className={BUTTON_BRAND}
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
            <Sparkle className="h-[15px] w-[15px]" weight="fill" aria-hidden />
            <span className="max-w-[22rem] truncate">{forecast.action.label}</span>
          </button>
        )}
        {onSnooze ? (
          <button
            type="button"
            className={BUTTON_OUTLINE}
            disabled={snoozing}
            title="Hide it for your whole team for a week"
            onClick={onSnooze}
          >
            {snoozing ? "Snoozing…" : "Snooze"}
          </button>
        ) : null}
        {onShare ? (
          <button type="button" className={BUTTON_OUTLINE} onClick={onShare}>
            <ShareNetwork className="h-4 w-4" aria-hidden />
            Share
          </button>
        ) : null}
        <span className="flex-1" />
        <button
          type="button"
          className="px-1.5 py-2.5 text-[13px] text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={rejecting || rejected}
          onClick={onReject}
        >
          {rejected ? `Marked not a real ${kindLower}` : rejecting ? "Saving…" : `Not a real ${kindLower}`}
        </button>
      </div>
    </article>
  )
}

export function ForecastList({
  forecasts,
  selectedKey,
  onSelect,
  snoozed = [],
  onUnsnooze,
}: {
  forecasts: Forecast[]
  selectedKey: string | null
  onSelect: (key: string) => void
  snoozed?: ForecastSnooze[]
  onUnsnooze?: (key: string) => void
}) {
  return (
    <section
      aria-labelledby="forecast-list-heading"
      className="flex flex-col gap-2.5 rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-[18px]"
    >
      <h2 id="forecast-list-heading" className={cn(INTEL.cardTitle, "px-1")}>
        All forecasts
      </h2>
      {forecasts.length === 0 ? (
        <p className={cn(TYPE.meta, "px-1")}>{snoozed.length > 0 ? "Every open forecast is snoozed." : "No forecasts for this department."}</p>
      ) : (
        <ul className="space-y-2.5">
          {forecasts.map((forecast) => {
            const on = forecast.key === selectedKey
            return (
              <li key={forecast.key}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => onSelect(forecast.key)}
                  className={cn(
                    "grid w-full grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[12px] border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    on
                      ? "border-[color:var(--g-text-primary)] bg-[color:var(--g-surface-2)]"
                      : "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] hover:border-[color:var(--g-text-primary)]",
                  )}
                >
                  <span
                    aria-hidden
                    className="h-[9px] w-[9px] shrink-0 rounded-full"
                    style={{ background: forecastDotColor(forecast) }}
                  />
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="block truncate text-[13.5px] font-medium text-foreground">{forecast.title}</span>
                    <span className="block truncate text-xs text-[color:var(--g-text-secondary)]">
                      {forecast.whenLabel}
                      {forecast.area ? ` · ${forecast.area}` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-[#33342f] dark:text-[color:var(--g-text-secondary)]">{formatPct(forecast.confidence)}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {snoozed.length > 0 ? (
        <div className="space-y-1.5 border-t border-[color:var(--g-background-muted)] px-1 pt-2.5">
          <p className="text-xs text-[color:var(--g-text-secondary)]">
            {snoozed.length} snoozed for your team. Each comes back on its own if it is still open.
          </p>
          <ul className="space-y-1">
            {snoozed.map((row) => (
              <li key={row.key} className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 truncate text-[color:var(--g-text-primary)]">
                  {row.title || "Forecast"}
                  <span className="text-[color:var(--g-text-secondary)]">
                    {" "}
                    · until {new Date(row.until).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </span>
                </span>
                {onUnsnooze ? (
                  <button
                    type="button"
                    className="shrink-0 font-medium text-[color:var(--g-brand-active)] underline underline-offset-2 dark:text-[color:var(--g-brand)]"
                    onClick={() => onUnsnooze(row.key)}
                  >
                    Bring back
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
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
      aria-describedby={forecast ? "forecast-outcome-target" : undefined}
      className="flex flex-col gap-3 rounded-[18px] bg-[#0b0c0c] p-5 text-[#efefea]"
    >
      <h2 id="forecast-outcome-heading" className="flex items-center gap-2 text-[15px] font-semibold">
        <Sparkle className="h-[15px] w-[15px] text-[#19c37d]" weight="fill" aria-hidden />
        Did it happen?
      </h2>
      <p className="text-[13px] leading-normal text-[#8a8b85]">
        Telling Gravitre how a forecast turned out is the fastest way to make the next one sharper.
      </p>
      {forecast ? (
        <p id="forecast-outcome-target" className="sr-only">
          For: {forecast.title}
        </p>
      ) : null}
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={disabled}
          aria-pressed={recorded === "happened"}
          onClick={() => onRecord("happened")}
          className="min-h-[39px] rounded-[10px] bg-[#19c37d] px-3 text-[13px] font-semibold text-[#06291a] transition-colors hover:bg-[#15ad6e] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          It happened
        </button>
        <button
          type="button"
          disabled={disabled}
          aria-pressed={recorded === "didnt"}
          onClick={() => onRecord("didnt")}
          className="min-h-[39px] rounded-[10px] border border-[#33342f] px-3 text-[13px] text-[#efefea] transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          It didn&apos;t
        </button>
      </div>
      {recorded ? (
        <p role="status" className="text-xs text-[#8a8b85]">
          Recorded: {recorded === "happened" ? "it happened" : "it didn't happen"}.
        </p>
      ) : null}
    </section>
  )
}
