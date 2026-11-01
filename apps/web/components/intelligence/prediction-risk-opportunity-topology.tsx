"use client"

/**
 * Forecasts › "What's coming, and when": risks above the line, opportunities
 * below, x = when (Today / 2 weeks / 1 month / 2 months +), dot size =
 * confidence. Forecasts without a date sit in a "No date yet" column rather
 * than being placed on a time we don't know.
 */
import { useMemo } from "react"
import {
  formatPct,
  layoutTimeline,
  TIMELINE_TICKS,
  UNDATED_X,
  type Forecast,
} from "@/components/intelligence/forecasts/forecast-model"
import { forecastDotColor } from "@/components/intelligence/forecasts/forecast-tone"
import { INTEL } from "@/components/intelligence/shell/intel-ui"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

const LANE_TOP = [12, 26, 39.3] // % of plot height, above the line
const LANE_BOTTOM = [62, 75.3, 88.7] // % of plot height, below the line

export function PredictionRiskOpportunityTopology({
  forecasts,
  areas,
  area,
  onAreaChange,
  selectedKey,
  onSelect,
  className,
}: {
  forecasts: Forecast[]
  areas: string[]
  area: string | null
  onAreaChange: (area: string | null) => void
  selectedKey: string | null
  onSelect: (key: string) => void
  className?: string
}) {
  const dots = useMemo(() => layoutTimeline(forecasts), [forecasts])
  const hasUndated = dots.some((dot) => dot.forecast.horizonDays == null)
  const plotted = dots.length

  return (
    <section
      aria-labelledby="forecast-timeline-heading"
      className={cn(INTEL.panel, "flex flex-col gap-4", className)}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 id="forecast-timeline-heading" className={INTEL.panelTitle}>
            What&apos;s coming, and when
          </h2>
          <p className={cn(INTEL.panelLead, "mt-1")}>
            Risks above the line, opportunities below. Bigger dot, more confident. Click one to see why.
          </p>
        </div>
        {areas.length > 0 ? (
          <div role="group" aria-label="Department" className="flex flex-wrap gap-1.5">
            {[null, ...areas].map((value) => {
              const on = area === value
              return (
                <button
                  key={value ?? "all"}
                  type="button"
                  aria-pressed={on}
                  onClick={() => onAreaChange(value)}
                  className={cn(INTEL.pill, on && INTEL.pillOn)}
                >
                  {value ?? "All departments"}
                </button>
              )
            })}
          </div>
        ) : null}
      </div>

      {plotted === 0 ? (
        <div className="rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-4 py-10 text-center">
          <p className="text-sm font-medium text-foreground">Nothing on the timeline yet</p>
          <p className={cn(TYPE.meta, "mt-1")}>
            Risks and opportunities appear here once Gravitre spots them in your connected sources and workflows.
          </p>
        </div>
      ) : (
        <div className="-mx-1 overflow-x-auto px-1 pb-1">
          <div className="flex min-w-[640px]">
            <div className="relative w-[108px] shrink-0" aria-hidden>
              <span className="absolute top-[25%] flex -translate-y-1/2 items-center gap-1.5 text-[13px] font-semibold text-[#8a5a06] dark:text-[color:var(--g-warning)]">
                <span className="h-2 w-2 rounded-full bg-[#d98a1f]" />
                Risks
              </span>
              <span className="absolute top-[75%] flex -translate-y-1/2 items-center gap-1.5 text-[13px] font-semibold text-[color:var(--g-emerald-deep)] dark:text-[color:var(--g-emerald)]">
                <span className="h-2 w-2 shrink-0 rounded-full bg-[color:var(--g-emerald)]" />
                Opportunities
              </span>
            </div>

            <div className="min-w-0 flex-1">
              <div className="relative h-[300px] border-l border-[color:var(--g-border-default)]">
                {TIMELINE_TICKS.slice(1).map((tick) => (
                  <div
                    key={tick.label}
                    aria-hidden
                    className="absolute inset-y-0 w-px bg-[color:var(--g-background-muted)]"
                    style={{ left: `${tick.x}%` }}
                  />
                ))}
                {hasUndated ? (
                  <div
                    aria-hidden
                    className="absolute inset-y-0 w-px border-l border-dashed border-[color:var(--g-border-default)]"
                    style={{ left: `${UNDATED_X - 4}%` }}
                  />
                ) : null}
                <div aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-foreground" />
                <span aria-hidden className="absolute left-1.5 top-1.5 font-mono text-[10.5px] uppercase text-[color:var(--g-text-primary)]">
                  Now
                </span>
                <div aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-[color:var(--g-border-strong)]" />

                <ul className="contents" aria-label="Forecasts on the timeline">
                  {dots.map((dot) => {
                    const f = dot.forecast
                    const on = f.key === selectedKey
                    const dimmed = area != null && f.area !== area
                    const top = (dot.side === "above" ? LANE_TOP : LANE_BOTTOM)[dot.lane] ?? 50
                    const flip = dot.flip
                    return (
                      <li key={f.key} className="contents">
                        <button
                          type="button"
                          onClick={() => onSelect(f.key)}
                          aria-pressed={on}
                          aria-label={`${f.kind === "risk" ? "Risk" : "Opportunity"}: ${f.title}, ${
                            f.confidence == null ? "confidence not scored" : `${Math.round(f.confidence * 100)} percent confident`
                          }, ${f.whenLabel}`}
                          className={cn(
                            "absolute flex max-w-[25%] -translate-y-1/2 items-center gap-2 whitespace-nowrap rounded-full border bg-[color:var(--g-surface-1)] py-[5px] pl-[5px] pr-3 text-[12.5px] transition-[opacity,box-shadow,border-color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            on
                              ? "z-10 border-[color:var(--g-text-primary)] shadow-[0_6px_18px_rgba(20,21,19,0.14)]"
                              : "border-[color:var(--g-border-default)] hover:border-[color:var(--g-text-primary)]",
                            flip && "flex-row-reverse pl-3 pr-[5px]",
                            dimmed && "opacity-25",
                          )}
                          style={
                            flip
                              ? { right: `${100 - dot.x}%`, top: `${top}%` }
                              : { left: `${Math.max(dot.x, 0.6)}%`, top: `${top}%` }
                          }
                        >
                          <span
                            aria-hidden
                            className="shrink-0 rounded-full"
                            style={{
                              width: dot.size,
                              height: dot.size,
                              background: forecastDotColor(f),
                            }}
                          />
                          <span className="truncate font-medium text-foreground" title={f.title}>{f.title}</span>
                          <span className="shrink-0 font-mono text-[11px] text-[color:var(--g-text-secondary)]">{formatPct(f.confidence)}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
              <div aria-hidden className="relative h-[22px] pt-2 font-mono text-[11px] text-[color:var(--g-text-secondary)]">
                {TIMELINE_TICKS.map((tick) => (
                  <span key={tick.label} className="absolute whitespace-nowrap" style={{ left: `${tick.x}%` }}>
                    {tick.label}
                  </span>
                ))}
                {hasUndated ? (
                  <span className="absolute whitespace-nowrap" style={{ left: `${UNDATED_X - 3}%` }}>
                    No date yet
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
