"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import type { IntelligenceOverview } from "@/lib/admin-intelligence"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Badge } from "@/components/ui/badge"
import { Stack, BookOpen, Warning } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate } from "./shared"

function relativeOrNull(value: string | null): string {
  if (!value) return "not seen recently"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return "not seen recently"
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function OverviewTab({ active }: { active: boolean }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR<IntelligenceOverview>(
    active ? "/api/admin/intelligence/overview" : null,
    fetcher,
    { revalidateOnFocus: false },
  )

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
        <div className="flex justify-end">
          <DataFreshness
            updatedAt={data?.generatedAt ?? undefined}
            isRefreshing={isValidating}
            onRefresh={() => mutate()}
          />
        </div>

        <SectionCard
          title="Query clusters"
          description="Groups of similar questions your users ask, so you can see what knowledge is in demand."
          icon={<Stack className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.clusters.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.clusters.map((cluster) => (
                <li key={cluster.id} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{cluster.label}</p>
                    {cluster.exampleQueries.length > 0 ? (
                      <p className="mt-0.5 truncate text-sm text-muted-foreground">
                        e.g. {cluster.exampleQueries.slice(0, 3).join(" · ")}
                      </p>
                    ) : null}
                  </div>
                  <Badge variant="secondary" className="shrink-0 tabular-nums">
                    {cluster.queryCount} queries
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <NotYetPopulated>
              Query clusters appear once your team has run enough searches for the engine to group
              similar questions together.
            </NotYetPopulated>
          )}
        </SectionCard>

        <SectionCard
          title="Glossary"
          description="Terms the engine has learned from your connected sources."
          icon={<BookOpen className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.glossary.length > 0 ? (
            <dl className="space-y-3">
              {data.glossary.map((term) => (
                <div key={term.id} className="rounded-xl border border-border bg-background/60 p-3">
                  <dt className="flex items-center justify-between gap-2 font-medium text-foreground">
                    {term.term}
                    <span className="text-xs font-normal text-muted-foreground">
                      {term.sourceCount} source{term.sourceCount === 1 ? "" : "s"}
                    </span>
                  </dt>
                  <dd className="mt-0.5 text-sm leading-relaxed text-muted-foreground text-pretty">
                    {term.definition}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <NotYetPopulated>
              The glossary builds itself as documents and data sources are indexed. Connect sources to
              start populating defined terms.
            </NotYetPopulated>
          )}
        </SectionCard>

        <SectionCard
          title="Knowledge gaps"
          description="Questions users asked that the engine couldn't answer well — your highest-value content to add next."
          icon={<Warning className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.gaps.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.gaps.map((gap) => (
                <li key={gap.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">{gap.topic}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Last asked {relativeOrNull(gap.lastSeenAt)}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0 border-amber-300 text-amber-700 tabular-nums">
                    {gap.missedQueries} missed
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <NotYetPopulated>
              No knowledge gaps detected yet. As users search, any questions the engine struggles with
              will surface here.
            </NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
