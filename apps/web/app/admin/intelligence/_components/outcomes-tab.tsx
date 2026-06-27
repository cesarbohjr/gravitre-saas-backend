"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { ChartLineUp } from "@phosphor-icons/react"
import { NotYetPopulated, readNumber, SectionCard, TabStateGate } from "./shared"

export function OutcomesTab({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? ["admin/intelligence/outcomes"] : null,
    () => intelligenceApi.outcomes(),
    { revalidateOnFocus: false },
  )

  const summaries = data?.agentSummaries ?? []
  const sufficient = summaries.filter((item) => item.sufficientData)
  const insufficient = summaries.filter((item) => !item.sufficientData)

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <SectionCard
        title="Outcome-linked learning"
        description="Correlational attribution only — not reinforcement learning. Win rates require minimum sample sizes."
        icon={<ChartLineUp className="h-5 w-5" weight="duotone" aria-hidden />}
      >
        <p className="text-xs text-muted-foreground text-pretty">
          {data?.scopeNote ?? data?.confidenceNote}
        </p>

        {summaries.length === 0 ? (
          <div className="mt-4">
            <NotYetPopulated>
              No outcome data yet. Baselines are recorded when agents act on HubSpot deals with observable amounts.
            </NotYetPopulated>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {sufficient.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2">
                {sufficient.map((summary) => (
                  <div key={summary.agentId} className="rounded-xl border border-border bg-background/60 p-4">
                    <p className="font-medium">{summary.agentName ?? summary.agentId}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">
                        win rate {(readNumber(summary.winRate) * 100).toFixed(0)}%
                      </Badge>
                      <Badge variant="outline">n={readNumber(summary.sampleSize)}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground text-pretty">{summary.confidenceNote}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {insufficient.length > 0 ? (
              <div className="rounded-xl border border-dashed border-border px-4 py-3">
                <p className="text-sm font-medium">Insufficient data</p>
                <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                  {insufficient.map((summary) => (
                    <li key={summary.agentId}>
                      {summary.agentName ?? summary.agentId}: {readNumber(summary.sampleSize)} /{" "}
                      {readNumber(summary.minSampleSize)} samples — {summary.message ?? "insufficient data"}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </SectionCard>
    </TabStateGate>
  )
}
