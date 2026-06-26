"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import type { RelationshipsData } from "@/lib/admin-intelligence"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Cube, Graph, ArrowRight } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, scoreColor, formatScore } from "./shared"
import { cn } from "@/lib/utils"

export function RelationshipsTab({ active }: { active: boolean }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR<RelationshipsData>(
    active ? "/api/admin/intelligence/relationships" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const [query, setQuery] = useState("")

  const filtered = useMemo(() => {
    const rels = data?.relationships ?? []
    const q = query.trim().toLowerCase()
    if (!q) return rels
    return rels.filter(
      (r) =>
        r.sourceName.toLowerCase().includes(q) ||
        r.targetName.toLowerCase().includes(q) ||
        r.type.toLowerCase().includes(q),
    )
  }, [data, query])

  const hasData = Boolean(data && (data.entities.length > 0 || data.relationships.length > 0))

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 font-medium">
              <Cube className="h-3.5 w-3.5" weight="duotone" aria-hidden />
              {data?.entities.length ?? 0} entities
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 font-medium">
              <Graph className="h-3.5 w-3.5" weight="duotone" aria-hidden />
              {data?.relationships.length ?? 0} relationships
            </span>
          </div>
          <DataFreshness
            updatedAt={data?.generatedAt ?? undefined}
            isRefreshing={isValidating}
            onRefresh={() => mutate()}
          />
        </div>

        <SectionCard
          title="Entity relationships"
          description="Connections the engine extracted between people, systems, and concepts across your knowledge — with how confident it is in each link."
          icon={<Graph className="h-5 w-5" weight="duotone" aria-hidden />}
          action={
            hasData ? (
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter relationships"
                className="h-9 w-48"
                aria-label="Filter relationships"
              />
            ) : null
          }
        >
          {hasData ? (
            filtered.length > 0 ? (
              <ul className="space-y-2">
                {filtered.map((r) => {
                  const { text } = scoreColor(r.confidence)
                  return (
                    <li
                      key={r.id}
                      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-border bg-background/60 px-3 py-2.5"
                    >
                      <span className="font-medium text-foreground">{r.sourceName}</span>
                      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <ArrowRight className="h-3.5 w-3.5" weight="bold" aria-hidden />
                        {r.type}
                        <ArrowRight className="h-3.5 w-3.5" weight="bold" aria-hidden />
                      </span>
                      <span className="font-medium text-foreground">{r.targetName}</span>
                      <span className="ml-auto flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground tabular-nums">{r.mentions} mentions</span>
                        <span
                          className={cn("rounded-full bg-secondary px-1.5 py-0.5 font-semibold tabular-nums", text)}
                          title="Extraction confidence"
                        >
                          {formatScore(r.confidence)}
                        </span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <NotYetPopulated>No relationships match &ldquo;{query}&rdquo;.</NotYetPopulated>
            )
          ) : (
            <NotYetPopulated>
              No relationships extracted yet. As the engine indexes your sources, it maps how entities
              connect and shows each link&apos;s extraction confidence here.
            </NotYetPopulated>
          )}
        </SectionCard>

        {hasData && data!.entities.length > 0 ? (
          <SectionCard
            title="Entities"
            description="Distinct things the engine recognizes, ranked by how often they appear."
            icon={<Cube className="h-5 w-5" weight="duotone" aria-hidden />}
          >
            <div className="flex flex-wrap gap-2">
              {data!.entities.map((e) => (
                <Badge key={e.id} variant="secondary" className="gap-1.5">
                  <span className="text-muted-foreground">{e.type}:</span>
                  {e.name}
                  <span className="tabular-nums text-muted-foreground">{e.mentions}</span>
                </Badge>
              ))}
            </div>
          </SectionCard>
        ) : null}
      </div>
    </TabStateGate>
  )
}
