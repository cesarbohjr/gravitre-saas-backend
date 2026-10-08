"use client"

import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { WarningCircle, Plugs } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"
import { SectionCard } from "./shared"

function pct(rate: number | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return "Not reported"
  return `${Math.round(rate * 100)}%`
}

export function ConnectorOpsCard() {
  const { data, isLoading, error, mutate } = useSWR(
    "admin/intelligence/connector-writes",
    () => intelligenceApi.connectorWrites({ periodDays: 7 }),
    { revalidateOnFocus: false },
  )

  const rows = data?.rows ?? []
  const spikes = data?.spikes ?? []
  const hasSpike = Boolean(data?.hasSpike || spikes.length > 0)

  return (
    <SectionCard
      title="Connector activity"
      description="Connected tool performance over the last 7 days: requests, successes, and failures."
      action={
        <Badge variant={hasSpike ? "destructive" : "secondary"} className="font-normal">
          {hasSpike ? `${spikes.length} spike${spikes.length === 1 ? "" : "s"}` : error ? "Unavailable" : isLoading ? "Loading…" : data?.hasSpike === false && rows.length > 0 ? "No spikes reported" : "Not reported"}
        </Badge>
      }
    >
      {error ? <WorkSectionErrorCard error={error} onRetry={() => void mutate()} /> : null}
      {isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Loading connector activity…</p>
      ) : data ? (
        <div className="space-y-4">
          {hasSpike ? (
            <div
              role="status"
              className="flex items-start gap-3 rounded-[8px] border border-destructive/30 bg-destructive/10 px-3 py-2.5"
            >
              <WarningCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" weight="duotone" aria-hidden />
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium text-destructive">
                  Failure spike: more than 10% of recent calls failed
                </p>
                <ul className="space-y-0.5 text-xs text-muted-foreground">
                  {spikes.slice(0, 5).map((s) => (
                    <li key={`${s.vendor}:${s.action}`} className="truncate">
                      <span className="font-medium text-foreground">{s.vendor}</span> ·{" "}
                      {String(s.action).replace(/_/g, " ")}: {pct(s.failedRate)} failed ({s.failed}/{s.n})
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}

          {rows.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Plugs className="h-4 w-4" weight="duotone" aria-hidden />
              {Array.isArray(data?.rows) ? "No connector tool calls in this period." : "Connector activity not reported."}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-[8px] border border-divide">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Vendor</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Requested</th>
                    <th className="px-3 py-2 font-medium">Succeeded</th>
                    <th className="px-3 py-2 font-medium">Failed</th>
                    <th className="px-3 py-2 font-medium">Success rate</th>
                    <th className="px-3 py-2 font-medium">Top error</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 25).map((row) => (
                    <tr
                      key={`${row.vendor}:${row.action}`}
                      className={cn(
                        "border-b border-border/40 last:border-0",
                        row.spike && "bg-destructive/5",
                      )}
                    >
                      <td className="px-3 py-2 font-medium">{row.vendor}</td>
                      <td className="max-w-[220px] truncate px-3 py-2 text-muted-foreground" title={row.action}>
                        {String(row.action).replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-2 tabular-nums">{row.requested}</td>
                      <td className="px-3 py-2 tabular-nums">{row.completed}</td>
                      <td className="px-3 py-2 tabular-nums">{row.failed}</td>
                      <td className="px-3 py-2 tabular-nums">{pct(row.successRate)}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {row.topErrorCodes?.[0]
                          ? `${row.topErrorCodes[0].code} (${row.topErrorCodes[0].count})`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </SectionCard>
  )
}
