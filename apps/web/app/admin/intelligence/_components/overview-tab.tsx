"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { IntelligenceSnapshot } from "@/lib/api"
import { ChartBar, BookOpen, Stack, Warning, ChatCircleDots } from "@phosphor-icons/react"
import { formatTime, readNumber } from "./shared"

type Row = Record<string, unknown>

export function OverviewTab({
  data,
  isLoading,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
}) {
  const volume = data?.queryVolume
  const clusters = (data?.clusters ?? []) as Row[]
  const gaps = (data?.knowledgeGaps ?? []) as Row[]
  const glossary = (data?.glossary ?? []) as Row[]
  const failedRecent = (data?.recentFailedSearches ?? []) as Row[]

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Logged queries</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{isLoading ? "…" : (volume?.totalLogged ?? 0)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Distinct normalized</CardDescription>
            <CardTitle className="text-2xl tabular-nums">
              {isLoading ? "…" : (volume?.distinctNormalized ?? 0)}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed searches</CardDescription>
            <CardTitle className="text-2xl tabular-nums text-amber-600">
              {isLoading ? "…" : (volume?.failedSearchCount ?? 0)}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Warning className="h-5 w-5 text-amber-500" weight="duotone" aria-hidden />
            <CardTitle>Knowledge gaps</CardTitle>
          </div>
          <CardDescription>Clustered failed-search themes with suggested documentation.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : gaps.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No clustered knowledge gaps yet. Gaps appear once query clusters accumulate enough failed searches.
            </p>
          ) : (
            gaps.map((gap) => (
              <div key={String(gap.id ?? gap.description)} className="rounded-lg border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="destructive">
                    {readNumber(gap.failed_query_count ?? gap.failedQueryCount)} failed
                  </Badge>
                  <Badge variant="outline">{String(gap.status ?? "open")}</Badge>
                </div>
                <p className="mt-2 font-medium">{String(gap.description ?? "")}</p>
                {gap.suggested_content || gap.suggestedContent ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {String(gap.suggested_content ?? gap.suggestedContent)}
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  Identified {formatTime(gap.identified_at ?? gap.identifiedAt)}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Stack className="h-5 w-5 text-primary" weight="duotone" aria-hidden />
            <CardTitle>Query clusters</CardTitle>
          </div>
          <CardDescription>Recurring query themes from normalized history (requires sufficient volume).</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : clusters.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No clusters yet. Clustering runs once there are roughly 40 distinct normalized queries.
            </p>
          ) : (
            <div className="space-y-3">
              {clusters.map((cluster) => (
                <div key={String(cluster.id ?? cluster.cluster_label)} className="rounded-lg border border-border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{String(cluster.cluster_label ?? "Theme")}</span>
                    <Badge variant="secondary">{readNumber(cluster.member_query_count)} queries</Badge>
                    {readNumber(cluster.failed_search_count) > 0 ? (
                      <Badge variant="outline">{readNumber(cluster.failed_search_count)} failed</Badge>
                    ) : null}
                  </div>
                  {Array.isArray(cluster.representative_queries) && cluster.representative_queries.length > 0 ? (
                    <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
                      {(cluster.representative_queries as string[]).slice(0, 4).map((q) => (
                        <li key={q}>{q}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" weight="duotone" aria-hidden />
            <CardTitle>Company glossary</CardTitle>
          </div>
          <CardDescription>
            Extracted terms remain <Badge variant="outline">candidate</Badge> until approved in Memory Promotion.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : glossary.length === 0 ? (
            <p className="text-sm text-muted-foreground">No glossary candidates extracted yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Term</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Freq</th>
                    <th className="py-2 pr-4 font-medium">Department</th>
                    <th className="py-2 pr-4 font-medium">Source</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {glossary.map((term) => (
                    <tr key={String(term.id ?? term.term)} className="border-b border-border">
                      <td className="py-2 pr-4 font-medium">{String(term.term ?? "")}</td>
                      <td className="py-2 pr-4">{String(term.term_type ?? "")}</td>
                      <td className="py-2 pr-4 tabular-nums">{String(term.frequency ?? 0)}</td>
                      <td className="py-2 pr-4">{String(term.associated_department ?? "—")}</td>
                      <td className="py-2 pr-4">{String(term.source ?? "")}</td>
                      <td className="py-2">
                        <Badge variant="secondary">{String(term.status ?? "candidate")}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ChatCircleDots className="h-5 w-5 text-primary" weight="duotone" aria-hidden />
            <CardTitle>Recent failed searches</CardTitle>
          </div>
          <CardDescription>Raw failed-search log (unclustered detail).</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : failedRecent.length === 0 ? (
            <p className="text-sm text-muted-foreground">No failed searches logged recently.</p>
          ) : (
            <ul className="space-y-2">
              {failedRecent.map((row) => (
                <li key={String(row.id ?? row.query_text)} className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex flex-wrap gap-2">
                    {row.surface ? <Badge variant="outline">{String(row.surface)}</Badge> : null}
                    {row.department ? <Badge variant="secondary">{String(row.department)}</Badge> : null}
                  </div>
                  <p className="mt-1">{String(row.query_text ?? row.normalized_query_text ?? "")}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{formatTime(row.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="flex items-start gap-2.5 rounded-xl border border-dashed border-border bg-secondary/40 px-4 py-3 text-sm text-muted-foreground">
        <ChartBar className="mt-0.5 h-4 w-4 shrink-0" weight="duotone" aria-hidden />
        <p className="leading-relaxed text-pretty">
          Query observability is advisory only. Glossary auto-promotion, memory writes, and retrieval ranking follow
          their own rules in the Memory Promotion and Evaluation tabs.
        </p>
      </div>
    </div>
  )
}
