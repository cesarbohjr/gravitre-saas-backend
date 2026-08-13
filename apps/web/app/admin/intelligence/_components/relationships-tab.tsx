"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { intelligenceApi, type IntelligenceSnapshot } from "@/lib/api"
import { entityTypeLabel, relationshipTypeLabel } from "@/lib/learning-ui-copy"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { Graph, ArrowRight, Archive, ArrowCounterClockwise } from "@phosphor-icons/react"
import { readNumber, SectionCard } from "./shared"

type Row = Record<string, unknown>
type SortKey = "recent" | "confidence" | "evidence"

const PAGE_SIZE = 20

function confidenceTone(value: number): string {
  if (value >= 0.75) return "border-emerald-300 text-emerald-700 dark:text-emerald-300"
  if (value >= 0.5) return "border-amber-300 text-amber-700 dark:text-amber-300"
  return "border-rose-300 text-rose-700 dark:text-rose-300"
}

function confidenceLabel(value: number): string {
  if (value >= 0.75) return "Strong"
  if (value >= 0.5) return "Moderate"
  return "Weak"
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
  const [query, setQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState<string>("all")
  const [sortKey, setSortKey] = useState<SortKey>("recent")
  const [page, setPage] = useState(0)
  const [showArchived, setShowArchived] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const glossary = (data?.glossary ?? []) as Row[]

  const glossaryById = useMemo(
    () => Object.fromEntries(glossary.map((term) => [String(term.id ?? ""), String(term.term ?? "")])),
    [glossary],
  )

  const listKey = enabled
    ? ["admin/intelligence/relationships-list", showArchived ? "archived" : "active"]
    : null
  const {
    data: listData,
    isLoading: listLoading,
    mutate: mutateList,
  } = useSWR(listKey, () =>
    intelligenceApi.relationships({
      includeArchived: showArchived,
      limit: 500,
    }),
  )

  const relationships = useMemo(() => {
    const fromApi = (listData?.relationships as Row[] | undefined) ?? []
    if (fromApi.length > 0) return fromApi
    return ((data?.entityRelationships ?? []) as Row[]).filter((r) =>
      showArchived ? true : !r.archived_at,
    )
  }, [listData, data?.entityRelationships, showArchived])

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

  const relationshipTypes = useMemo(() => {
    const set = new Set<string>()
    for (const rel of relationships) {
      const t = String(rel.relationship_type ?? "").trim()
      if (t) set.add(t)
    }
    return [...set].sort()
  }, [relationships])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let rows = relationships.filter((rel) => {
      if (typeFilter !== "all" && String(rel.relationship_type ?? "") !== typeFilter) return false
      if (!q) return true
      const hay = [
        labelFor(rel.source_entity_type, rel.source_entity_id),
        labelFor(rel.target_entity_type, rel.target_entity_id),
        String(rel.relationship_type ?? ""),
        String(rel.source_entity_type ?? ""),
        String(rel.target_entity_type ?? ""),
      ]
        .join(" ")
        .toLowerCase()
      return hay.includes(q)
    })
    rows = [...rows].sort((a, b) => {
      if (sortKey === "confidence") return readNumber(b.confidence) - readNumber(a.confidence)
      if (sortKey === "evidence") return readNumber(b.evidence_count) - readNumber(a.evidence_count)
      const at = new Date(String(a.last_observed_at ?? a.created_at ?? 0)).getTime()
      const bt = new Date(String(b.last_observed_at ?? b.created_at ?? 0)).getTime()
      return (Number.isFinite(bt) ? bt : 0) - (Number.isFinite(at) ? at : 0)
    })
    return rows
  }, [relationships, query, typeFilter, sortKey, glossaryById])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

  async function setArchived(id: string, archived: boolean) {
    setBusyId(id)
    try {
      const res = await intelligenceApi.setRelationshipArchived(id, archived)
      if (!res?.ok) {
        toast.error(archived ? "Could not archive relationship" : "Could not restore relationship")
        return
      }
      toast.success(archived ? "Relationship archived" : "Relationship restored")
      await mutateList()
    } catch {
      toast.error("Request failed — try again")
    } finally {
      setBusyId(null)
    }
  }

  const loading = isLoading || listLoading

  return (
    <div className="space-y-6">
      <SectionCard
        title="Business relationships"
        description="Connections Gravitre has learned between terms, agents, and work in your org. Archive noise; keep the links that help agents stay consistent."
        icon={<Graph className="h-5 w-5" weight="duotone" aria-hidden />}
        action={
          <Badge variant="outline" className="font-normal tabular-nums">
            {filtered.length} shown
            {relationships.length !== filtered.length ? ` of ${relationships.length}` : ""}
          </Badge>
        }
      >
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading relationships…</p>
        ) : relationships.length === 0 && !showArchived ? (
          <p className="text-sm leading-relaxed text-muted-foreground text-pretty">
            No relationships yet. They appear as company intelligence runs over your indexed sources and glossary.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
              <div className="min-w-0 flex-1 space-y-1.5">
                <label htmlFor="rel-search" className="text-xs font-medium text-muted-foreground">
                  Search
                </label>
                <Input
                  id="rel-search"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setPage(0)
                  }}
                  placeholder="Search terms, types, or IDs…"
                  className="max-w-md"
                />
              </div>
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Relationship type</span>
                <Select
                  value={typeFilter}
                  onValueChange={(v) => {
                    setTypeFilter(v)
                    setPage(0)
                  }}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="All types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    {relationshipTypes.map((t) => (
                      <SelectItem key={t} value={t}>
                        {relationshipTypeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Sort</span>
                <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="recent">Most recent</SelectItem>
                    <SelectItem value="confidence">Confidence</SelectItem>
                    <SelectItem value="evidence">Evidence count</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                type="button"
                variant={showArchived ? "secondary" : "outline"}
                size="sm"
                onClick={() => {
                  setShowArchived((v) => !v)
                  setPage(0)
                }}
              >
                {showArchived ? "Showing archived" : "Show archived"}
              </Button>
            </div>

            {glossary.length > 0 ? (
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <span className="text-sm text-muted-foreground">Inspect glossary term</span>
                <Select value={selectedGlossaryId || undefined} onValueChange={setSelectedGlossaryId}>
                  <SelectTrigger className="w-full sm:w-[280px]">
                    <SelectValue placeholder="Select a term" />
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
              <div className="rounded-2xl border border-border bg-secondary/25 p-4">
                <p className="font-medium">
                  Related to &quot;{glossaryById[selectedGlossaryId] ?? selectedGlossaryId}&quot;
                </p>
                <ul className="mt-3 space-y-2 text-sm">
                  {detailRels.map((rel) => (
                    <li
                      key={`${rel.entityType}-${rel.entityId}-${rel.relationshipType}`}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <Badge variant="outline">{relationshipTypeLabel(rel.relationshipType)}</Badge>
                      <span>
                        {entityTypeLabel(rel.entityType)}:{" "}
                        {String(rel.entityLabel ?? rel.entityId ?? "")}
                      </span>
                      <Badge variant="secondary">{readNumber(rel.evidenceCount)} sources</Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground">No relationships match these filters.</p>
            ) : (
              <>
                <AdaptiveDataView className="border-0">
                  <div className="overflow-x-auto rounded-xl border border-border/60">
                    <table className="w-full min-w-[720px] text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-muted-foreground">
                          <th className="px-3 py-2.5 font-medium">From</th>
                          <th className="px-3 py-2.5 font-medium">Link</th>
                          <th className="px-3 py-2.5 font-medium">To</th>
                          <th className="px-3 py-2.5 font-medium">Evidence</th>
                          <th className="px-3 py-2.5 font-medium">Confidence</th>
                          <th className="px-3 py-2.5 font-medium">
                            <span className="sr-only">Actions</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {pageRows.map((rel) => {
                          const confidence = readNumber(rel.confidence)
                          const id = String(rel.id ?? "")
                          const archived = Boolean(rel.archived_at)
                          return (
                            <tr key={id || JSON.stringify(rel)} className="border-b border-border/70 last:border-0">
                              <td className="px-3 py-2.5">
                                <span className="text-xs text-muted-foreground">
                                  {entityTypeLabel(rel.source_entity_type)}
                                </span>
                                <p className="font-medium text-foreground text-pretty">
                                  {labelFor(rel.source_entity_type, rel.source_entity_id)}
                                </p>
                              </td>
                              <td className="px-3 py-2.5">
                                <span className="inline-flex items-center gap-1 text-muted-foreground">
                                  <ArrowRight className="h-3.5 w-3.5 shrink-0" weight="bold" aria-hidden />
                                  {relationshipTypeLabel(rel.relationship_type)}
                                </span>
                              </td>
                              <td className="px-3 py-2.5">
                                <span className="text-xs text-muted-foreground">
                                  {entityTypeLabel(rel.target_entity_type)}
                                </span>
                                <p className="font-medium text-foreground text-pretty">
                                  {labelFor(rel.target_entity_type, rel.target_entity_id)}
                                </p>
                              </td>
                              <td className="px-3 py-2.5 tabular-nums">{readNumber(rel.evidence_count)}</td>
                              <td className="px-3 py-2.5">
                                <Badge
                                  variant="outline"
                                  className={`tabular-nums ${confidenceTone(confidence)}`}
                                  title={`${confidence.toFixed(2)} (estimate)`}
                                >
                                  {confidenceLabel(confidence)}
                                </Badge>
                              </td>
                              <td className="px-3 py-2.5 text-right">
                                {id ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    className="gap-1.5"
                                    disabled={busyId === id}
                                    onClick={() => setArchived(id, !archived)}
                                  >
                                    {archived ? (
                                      <>
                                        <ArrowCounterClockwise className="h-4 w-4" weight="bold" aria-hidden />
                                        Restore
                                      </>
                                    ) : (
                                      <>
                                        <Archive className="h-4 w-4" weight="bold" aria-hidden />
                                        Archive
                                      </>
                                    )}
                                  </Button>
                                ) : null}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </AdaptiveDataView>

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Page {safePage + 1} of {pageCount}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={safePage <= 0}
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={safePage >= pageCount - 1}
                      onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </SectionCard>
    </div>
  )
}
