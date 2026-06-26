"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import {
  AlertTriangle,
  BookOpen,
  Layers,
  Link2,
  MessageSquareWarning,
  RefreshCw,
  Search,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function formatTime(value: unknown): string {
  if (!value || typeof value !== "string") return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "—"
  return parsed.toLocaleString()
}

export default function AdminIntelligencePage() {
  const { user } = useAuth()
  const [selectedGlossaryId, setSelectedGlossaryId] = useState<string>("")
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    user ? ["admin/intelligence/snapshot"] : null,
    () => intelligenceApi.snapshot()
  )
  const relationshipKey =
    user && selectedGlossaryId
      ? (["admin/intelligence/relationships", selectedGlossaryId] as const)
      : null
  const { data: relationshipDetail } = useSWR(relationshipKey, () =>
    intelligenceApi.relationships({
      entityType: "glossary_term",
      entityId: selectedGlossaryId,
    })
  )

  if (!user) {
    return (
      <AppShell title="Intelligence">
        <EmptyState title="Sign in required" description="Log in to view org intelligence." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load intelligence data."
    return (
      <AppShell title="Intelligence">
        <ErrorState title="Unable to load intelligence" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  const volume = data?.queryVolume
  const clusters = data?.clusters ?? []
  const glossary = data?.glossary ?? []
  const gaps = data?.knowledgeGaps ?? []
  const failedRecent = data?.recentFailedSearches ?? []
  const relationships = data?.entityRelationships ?? []
  const glossaryById = useMemo(
    () => Object.fromEntries(glossary.map((term) => [String(term.id ?? ""), String(term.term ?? "")])),
    [glossary]
  )

  return (
    <AppShell
      title="Intelligence"
      subtitle="Query observability, clusters, glossary, and knowledge gaps (advisory only)"
      actions={
        <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isValidating ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6 p-4 md:p-6">
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Logged queries</CardDescription>
              <CardTitle className="text-2xl">{isLoading ? "…" : volume?.totalLogged ?? 0}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Distinct normalized</CardDescription>
              <CardTitle className="text-2xl">{isLoading ? "…" : volume?.distinctNormalized ?? 0}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Failed searches</CardDescription>
              <CardTitle className="text-2xl text-amber-600">
                {isLoading ? "…" : volume?.failedSearchCount ?? 0}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <CardTitle>Knowledge Gaps</CardTitle>
            </div>
            <CardDescription>
              Clustered failed-search themes with suggested documentation (most actionable v3 output).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : gaps.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No clustered knowledge gaps yet. Gaps appear when query clusters accumulate enough failed searches.
              </p>
            ) : (
              gaps.map((gap) => (
                <div key={String(gap.id ?? gap.description)} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="destructive">{gap.failed_query_count ?? gap.failedQueryCount ?? 0} failed</Badge>
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
              <Layers className="h-5 w-5" />
              <CardTitle>Query Clusters</CardTitle>
            </div>
            <CardDescription>Recurring query themes from normalized history (requires sufficient volume).</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : clusters.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No clusters yet — need at least ~40 distinct normalized queries before clustering runs.
              </p>
            ) : (
              <div className="space-y-3">
                {clusters.map((cluster) => (
                  <div key={String(cluster.id ?? cluster.cluster_label)} className="rounded-lg border p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{String(cluster.cluster_label ?? "Theme")}</span>
                      <Badge variant="secondary">{cluster.member_query_count ?? 0} queries</Badge>
                      {(cluster.failed_search_count ?? 0) > 0 ? (
                        <Badge variant="outline">{cluster.failed_search_count} failed</Badge>
                      ) : null}
                    </div>
                    {Array.isArray(cluster.representative_queries) && cluster.representative_queries.length > 0 ? (
                      <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
                        {cluster.representative_queries.slice(0, 4).map((q: string) => (
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
              <BookOpen className="h-5 w-5" />
              <CardTitle>Company Glossary</CardTitle>
            </div>
            <CardDescription>
              Extracted terms remain <Badge variant="outline">candidate</Badge> until v4 approval workflow.
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
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 pr-4">Term</th>
                      <th className="py-2 pr-4">Type</th>
                      <th className="py-2 pr-4">Freq</th>
                      <th className="py-2 pr-4">Department</th>
                      <th className="py-2 pr-4">Source</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {glossary.map((term) => (
                      <tr key={String(term.id ?? term.term)} className="border-b">
                        <td className="py-2 pr-4 font-medium">{String(term.term ?? "")}</td>
                        <td className="py-2 pr-4">{String(term.term_type ?? "")}</td>
                        <td className="py-2 pr-4">{String(term.frequency ?? 0)}</td>
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
              <Link2 className="h-5 w-5" />
              <CardTitle>Entity Relationships</CardTitle>
            </div>
            <CardDescription>
              One-hop related entities from v3/v4 signal (list view — not a graph visualization).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : relationships.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No relationships yet — rebuilt when company intelligence runs.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm text-muted-foreground">Inspect glossary term:</span>
                  <Select value={selectedGlossaryId} onValueChange={setSelectedGlossaryId}>
                    <SelectTrigger className="w-[280px]">
                      <SelectValue placeholder="Select a glossary term" />
                    </SelectTrigger>
                    <SelectContent>
                      {glossary.map((term) => (
                        <SelectItem key={String(term.id)} value={String(term.id)}>
                          {String(term.term ?? term.id)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {selectedGlossaryId && relationshipDetail?.relationships ? (
                  <div className="rounded-lg border p-4">
                    <p className="font-medium">
                      One-hop neighbors for &quot;{glossaryById[selectedGlossaryId] ?? selectedGlossaryId}&quot;
                    </p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {(relationshipDetail.relationships as Array<Record<string, unknown>>).map((rel) => (
                        <li key={`${rel.entityType}-${rel.entityId}-${rel.relationshipType}`} className="flex flex-wrap gap-2">
                          <Badge variant="outline">{String(rel.relationshipType ?? "")}</Badge>
                          <span>
                            {String(rel.entityType ?? "")}: {String(rel.entityLabel ?? rel.entityId ?? "")}
                          </span>
                          <Badge variant="secondary">evidence {String(rel.evidenceCount ?? 0)}</Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-2 pr-4">Source</th>
                        <th className="py-2 pr-4">Relationship</th>
                        <th className="py-2 pr-4">Target</th>
                        <th className="py-2 pr-4">Evidence</th>
                        <th className="py-2">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {relationships.slice(0, 30).map((rel) => (
                        <tr key={String(rel.id)} className="border-b">
                          <td className="py-2 pr-4">
                            {String(rel.source_entity_type ?? "")} /{" "}
                            {rel.source_entity_type === "glossary_term"
                              ? glossaryById[String(rel.source_entity_id ?? "")] ?? rel.source_entity_id
                              : rel.source_entity_id}
                          </td>
                          <td className="py-2 pr-4">{String(rel.relationship_type ?? "")}</td>
                          <td className="py-2 pr-4">
                            {String(rel.target_entity_type ?? "")} /{" "}
                            {rel.target_entity_type === "glossary_term"
                              ? glossaryById[String(rel.target_entity_id ?? "")] ?? rel.target_entity_id
                              : rel.target_entity_id}
                          </td>
                          <td className="py-2 pr-4">{String(rel.evidence_count ?? 0)}</td>
                          <td className="py-2">{String(rel.confidence ?? 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <MessageSquareWarning className="h-5 w-5" />
              <CardTitle>Recent Failed Searches</CardTitle>
            </div>
            <CardDescription>Raw failed-search log from v2 (unclustered detail).</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : failedRecent.length === 0 ? (
              <p className="text-sm text-muted-foreground">No failed searches logged recently.</p>
            ) : (
              <ul className="space-y-2">
                {failedRecent.map((row) => (
                  <li key={String(row.id ?? row.query_text)} className="rounded border p-3 text-sm">
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

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              <CardTitle>Advisory scope</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            v6 adds a lightweight relationship layer (one-hop only). Glossary auto-promotion, memory writes,
            and retrieval ranking follow v4/v5 rules separately.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
