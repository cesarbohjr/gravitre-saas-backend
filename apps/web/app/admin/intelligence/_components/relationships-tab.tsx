"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { intelligenceApi, type IntelligenceSnapshot } from "@/lib/api"
import { Graph, ArrowRight } from "@phosphor-icons/react"
import { readNumber } from "./shared"

type Row = Record<string, unknown>

function confidenceTone(value: number): string {
  if (value >= 0.75) return "border-emerald-300 text-emerald-700"
  if (value >= 0.5) return "border-amber-300 text-amber-700"
  return "border-rose-300 text-rose-700"
}

export function RelationshipsTab({
  data,
  isLoading,
  enabled,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
  enabled: boolean
}) {
  const [selectedGlossaryId, setSelectedGlossaryId] = useState<string>("")
  const glossary = (data?.glossary ?? []) as Row[]
  const relationships = (data?.entityRelationships ?? []) as Row[]

  const glossaryById = useMemo(
    () => Object.fromEntries(glossary.map((term) => [String(term.id ?? ""), String(term.term ?? "")])),
    [glossary],
  )

  const { data: detail } = useSWR(
    enabled && selectedGlossaryId ? ["admin/intelligence/relationships", selectedGlossaryId] : null,
    () => intelligenceApi.relationships({ entityType: "glossary_term", entityId: selectedGlossaryId }),
  )
  const detailRels = (detail?.relationships as Row[] | undefined) ?? []

  function labelFor(entityType: unknown, entityId: unknown): string {
    if (entityType === "glossary_term") {
      return glossaryById[String(entityId ?? "")] ?? String(entityId ?? "")
    }
    return String(entityId ?? "")
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Graph className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
          <CardTitle>Entity relationships</CardTitle>
        </div>
        <CardDescription>
          One-hop related entities from company intelligence. Each edge carries an extraction confidence (list view,
          not a graph visualization).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : relationships.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No relationships yet. The graph is rebuilt when company intelligence runs over your indexed sources.
          </p>
        ) : (
          <>
            {glossary.length > 0 ? (
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
            ) : null}

            {selectedGlossaryId && detailRels.length > 0 ? (
              <div className="rounded-lg border border-border bg-secondary/30 p-4">
                <p className="font-medium">
                  One-hop neighbors for &quot;{glossaryById[selectedGlossaryId] ?? selectedGlossaryId}&quot;
                </p>
                <ul className="mt-3 space-y-2 text-sm">
                  {detailRels.map((rel) => (
                    <li
                      key={`${rel.entityType}-${rel.entityId}-${rel.relationshipType}`}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <Badge variant="outline">{String(rel.relationshipType ?? "")}</Badge>
                      <span>
                        {String(rel.entityType ?? "")}: {String(rel.entityLabel ?? rel.entityId ?? "")}
                      </span>
                      <Badge variant="secondary">evidence {readNumber(rel.evidenceCount)}</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Source</th>
                    <th className="py-2 pr-4 font-medium">Relationship</th>
                    <th className="py-2 pr-4 font-medium">Target</th>
                    <th className="py-2 pr-4 font-medium">Evidence</th>
                    <th className="py-2 font-medium">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {relationships.slice(0, 50).map((rel) => {
                    const confidence = readNumber(rel.confidence)
                    return (
                      <tr key={String(rel.id)} className="border-b border-border">
                        <td className="py-2 pr-4">
                          <span className="text-muted-foreground">{String(rel.source_entity_type ?? "")}</span>{" "}
                          {labelFor(rel.source_entity_type, rel.source_entity_id)}
                        </td>
                        <td className="py-2 pr-4">
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <ArrowRight className="h-3.5 w-3.5" weight="bold" aria-hidden />
                            {String(rel.relationship_type ?? "")}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className="text-muted-foreground">{String(rel.target_entity_type ?? "")}</span>{" "}
                          {labelFor(rel.target_entity_type, rel.target_entity_id)}
                        </td>
                        <td className="py-2 pr-4 tabular-nums">{readNumber(rel.evidence_count)}</td>
                        <td className="py-2">
                          <Badge variant="outline" className={`tabular-nums ${confidenceTone(confidence)}`}>
                            {confidence.toFixed(2)}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
