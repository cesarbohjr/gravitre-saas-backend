"use client"

import { useMemo } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ArrowRight, ChevronDown } from "lucide-react"
import { workflowsApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { connectorVendorKey, formatVendorLabel } from "@/lib/connectors"
import { useSectionCollapsed } from "@/lib/dashboard/view-preference"
import { cn } from "@/lib/utils"

type ConnectorOutcome = { connector: string; pass: number; fail: number; cancel: number; pass_rate: number | null }

type OpsSummary = {
  window_hours?: number
  totals?: { pass: number; fail: number; cancel: number }
  by_connector?: ConnectorOutcome[]
  event_count?: number
}

/** Rows shown in the preview; the full ledger lives on the Activity page. */
export const SYSTEM_OUTCOMES_PREVIEW = 3

/**
 * Systems ranked by attention: any failure first, then by volume. A system that is
 * failing is the reason this section exists, so it must never be cut from the preview.
 */
export function rankSystemOutcomes(rows: ConnectorOutcome[] | undefined): ConnectorOutcome[] {
  return (rows ?? [])
    .filter((row) => row.connector && row.pass + row.fail + row.cancel > 0)
    .sort((a, b) => {
      if ((b.fail > 0 ? 1 : 0) !== (a.fail > 0 ? 1 : 0)) return (b.fail > 0 ? 1 : 0) - (a.fail > 0 ? 1 : 0)
      return b.pass + b.fail + b.cancel - (a.pass + a.fail + a.cancel)
    })
}

/**
 * Governed execution outcomes per connected system (ops-summary, 24h window), as a
 * collapsible preview. Counts only: the outcome ledger carries no revenue
 * attribution, so no currency is shown. Hidden until something has executed.
 */
export function SystemOutcomes({ className }: { className?: string }) {
  const [collapsed, toggle] = useSectionCollapsed("system-outcomes")
  const { data } = useSWR(
    ["execution-outcomes-ops-summary"],
    () => workflowsApi.executionOutcomesOpsSummary(),
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
  const summary = data as OpsSummary | undefined
  const ranked = useMemo(() => rankSystemOutcomes(summary?.by_connector), [summary])
  if (ranked.length === 0) return null

  const hours = summary?.window_hours ?? 24
  const events = summary?.event_count ?? 0
  const failing = ranked.filter((row) => row.fail > 0).length
  const preview = ranked.slice(0, SYSTEM_OUTCOMES_PREVIEW)
  const hidden = ranked.length - preview.length

  return (
    <section
      aria-labelledby="system-outcomes-heading"
      data-review-surface="system-outcomes"
      data-collapsed={collapsed ? "" : undefined}
      className={cn("flex flex-col gap-3", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="system-outcomes-body"
          className="-ml-1 inline-flex min-h-9 items-center gap-1.5 rounded-[6px] px-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronDown
            aria-hidden
            className={cn("size-4 text-muted-foreground transition-transform motion-reduce:transition-none", collapsed && "-rotate-90")}
          />
          <h3 id="system-outcomes-heading" className="text-[13px] font-semibold text-foreground">
            Execution outcomes by system
          </h3>
          <span
            className={cn(
              "ml-1 rounded-full px-2 text-[11.5px] font-medium tabular-nums leading-5",
              failing > 0
                ? "bg-destructive/12 text-destructive"
                : "bg-[color:var(--g-brand)]/12 text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
            )}
          >
            {failing > 0 ? `${failing} failing` : "All passing"}
          </span>
        </button>
        <span className="text-[11.5px] text-muted-foreground">
          {events} governed executions · last {hours}h
        </span>
      </div>

      {collapsed ? null : (
        <div id="system-outcomes-body" className="flex flex-col gap-2">
          <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
            {preview.map((row) => {
              const total = row.pass + row.fail + row.cancel
              const label = formatVendorLabel(connectorVendorKey(row.connector))
              return (
                <li key={row.connector} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto] items-center gap-3 py-2 text-[12px]">
                  <span className="min-w-0 truncate font-medium text-foreground">{label}</span>
                  <span
                    className="flex h-2 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]"
                    role="img"
                    aria-label={`${label}: ${row.pass} passed, ${row.fail} failed, ${row.cancel} cancelled`}
                  >
                    <span className="bg-[color:var(--g-brand)]" style={{ width: `${(row.pass / total) * 100}%` }} />
                    <span className="bg-destructive" style={{ width: `${(row.fail / total) * 100}%` }} />
                    <span className="bg-muted-foreground/40" style={{ width: `${(row.cancel / total) * 100}%` }} />
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {row.pass} passed
                    {row.fail > 0 ? <span className="text-destructive"> · {row.fail} failed</span> : null}
                    {row.cancel > 0 ? ` · ${row.cancel} cancelled` : null}
                    {row.pass_rate != null ? (
                      <span className="ml-2 font-medium text-foreground" title="Pass rate: passed ÷ (passed + failed)">
                        {Math.round(row.pass_rate * 100)}%
                      </span>
                    ) : null}
                  </span>
                </li>
              )
            })}
          </ul>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
            <Link
              href={APP_ROUTES.activity}
              className="inline-flex min-h-9 items-center gap-1 font-medium text-[color:var(--g-brand-active)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-[color:var(--g-brand)]"
            >
              {hidden > 0 ? `View all ${ranked.length} systems in Activity` : "View all in Activity"}
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
            {failing > 0 ? (
              <Link
                href={`${APP_ROUTES.activity}?tab=failures`}
                className="inline-flex min-h-9 items-center gap-1 text-muted-foreground hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Review failures
                <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            ) : null}
          </div>
        </div>
      )}
    </section>
  )
}
