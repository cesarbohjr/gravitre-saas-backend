"use client"

/**
 * Evidence behind "Revenue opportunities": the open HubSpot deals that make up
 * the number, each linking to its record, plus how it is counted. Open Stripe
 * invoices appear apart, as money to collect.
 */
import Link from "next/link"
import { ArrowSquareOut, ArrowsClockwise } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { formatMoneyCompact } from "@/components/intelligence/overview/overview-model"
import type { RevenueOpportunities } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

function money(value: number, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(value)
}

function closes(date: string, past: boolean): string {
  const at = new Date(`${date}T00:00:00Z`)
  if (Number.isNaN(at.getTime())) return ""
  const label = at.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })
  return past ? `close date ${label} has passed` : `closes ${label}`
}

export function RevenueOpportunitiesSheet({
  open,
  onOpenChange,
  data,
  refreshing,
  onRefresh,
  connectorsHref,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  data: RevenueOpportunities | null | undefined
  refreshing: boolean
  onRefresh: () => void
  connectorsHref: string
}) {
  const ready = data?.status === "ready"
  const others = Object.entries(data?.otherCurrencies ?? {})
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-md">
        <SheetHeader className="border-b border-divide">
          <SheetTitle>Revenue opportunities</SheetTitle>
          <SheetDescription>
            Gravitre found these in HubSpot. It counts only amounts that exist in your systems, never estimates of what a
            deal might grow to.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-5 p-4">
          {!ready ? (
            <div className="space-y-3">
              <p className={TYPE.bodyMuted}>
                {data?.status === "not_connected"
                  ? "HubSpot isn't connected, so there are no deal amounts to count yet."
                  : (data?.error ?? "HubSpot couldn't be read just now.")}
              </p>
              <Button asChild size="sm" variant="outline">
                <Link href={connectorsHref}>{data?.status === "not_connected" ? "Connect HubSpot" : "Open Connectors"}</Link>
              </Button>
            </div>
          ) : (
            <>
              <div>
                <p className="text-[34px] font-semibold leading-none tracking-[-0.02em] tabular-nums text-[color:var(--g-text-primary)]">
                  {data.total != null ? formatMoneyCompact(data.total, data.currency) : "No amounts yet"}
                </p>
                <p className={cn(TYPE.meta, "mt-1.5")}>open, closing in the next {data.lookaheadDays} days</p>
              </div>
              {data.rows.length > 0 ? (
                <ul className="divide-y divide-[color:var(--g-border-subtle)] rounded-[var(--np-radius-md)] border border-[color:var(--g-border-subtle)]">
                  {data.rows.map((row) => (
                    <li key={row.id} className="flex items-start justify-between gap-3 px-3 py-2.5">
                      <div className="min-w-0">
                        {row.href ? (
                          <a
                            href={row.href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm font-medium text-[color:var(--g-text-primary)] hover:underline"
                          >
                            {row.label}
                            <ArrowSquareOut className="h-3 w-3 shrink-0" aria-hidden />
                          </a>
                        ) : (
                          <p className="text-sm font-medium text-[color:var(--g-text-primary)]">{row.label}</p>
                        )}
                        <p className={cn(TYPE.meta, "mt-0.5")}>
                          {row.kind} · {row.source} · {closes(row.closeDate, row.pastCloseDate)}
                        </p>
                      </div>
                      <span className="shrink-0 text-sm font-semibold tabular-nums text-[color:var(--g-text-primary)]">
                        {money(row.amount, row.currency)}
                      </span>
                    </li>
                  ))}
                  {data.moreCount > 0 ? (
                    <li className={cn(TYPE.meta, "px-3 py-2.5")}>
                      And {data.moreCount} smaller {data.moreCount === 1 ? "deal" : "deals"}, included in the total.
                    </li>
                  ) : null}
                </ul>
              ) : (
                <p className={TYPE.bodyMuted}>No open deals with an amount close in the next {data.lookaheadDays} days.</p>
              )}
              {data.unpricedCount > 0 || others.length > 0 ? (
                <p className={TYPE.meta}>
                  {data.unpricedCount > 0
                    ? `${data.unpricedCount} open ${data.unpricedCount === 1 ? "deal has" : "deals have"} no amount in HubSpot, so ${data.unpricedCount === 1 ? "it isn't" : "they aren't"} counted. `
                    : ""}
                  {others.length > 0
                    ? `Deals in ${others.map(([c, v]) => `${c} (${money(v, c)})`).join(", ")} are kept apart, not converted.`
                    : ""}
                </p>
              ) : null}
              {data.toCollect && data.toCollect.count > 0 ? (
                <div className="rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-3 py-2.5">
                  <p className="text-sm font-medium text-[color:var(--g-text-primary)]">
                    {money(data.toCollect.total, data.toCollect.currency)} to collect
                  </p>
                  <p className={cn(TYPE.meta, "mt-0.5")}>
                    {data.toCollect.count} open Stripe {data.toCollect.count === 1 ? "invoice" : "invoices"}
                    {data.toCollect.overdueCount > 0 ? `, ${data.toCollect.overdueCount} past due` : ""}. Counted
                    separately, not as new revenue.
                  </p>
                </div>
              ) : null}
            </>
          )}
          <div className="space-y-1.5 border-t border-[color:var(--g-border-subtle)] pt-4">
            <p className={cn(TYPE.meta, "font-semibold uppercase tracking-[0.08em]")}>How it is counted</p>
            <p className={TYPE.bodyMuted}>{data?.method ?? "Sum of open HubSpot deal amounts closing soon."}</p>
          </div>
          <Button size="sm" variant="outline" onClick={onRefresh} disabled={refreshing}>
            <ArrowsClockwise className={cn("mr-1.5 h-3.5 w-3.5", refreshing && "animate-spin")} aria-hidden />
            {refreshing ? "Reading HubSpot…" : "Read HubSpot again"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
