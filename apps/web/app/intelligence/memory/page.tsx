"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { Brain, ArrowCounterClockwise } from "@phosphor-icons/react"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi, memoryPromotionApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { plainDecisionReasoning, readString } from "@/lib/intelligence/helpers"
import { MemoryCategoryChip } from "@/components/intelligence/memory-category-chip"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

const copy = SURFACE_COPY.pages.memory

type MemoryLens = "org" | "auto" | "graph"

const LENSES: { id: MemoryLens; label: string }[] = [
  { id: "org", label: copy.tabPromoted },
  { id: "auto", label: copy.tabAuto },
  { id: "graph", label: copy.tabGraph },
]

function RelationshipsLens() {
  const { data, isLoading } = useSWR("intelligence/memory/relationships", () => intelligenceApi.relationships())
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading relationships…</p>
  const rows = (data?.relationships as Array<Record<string, unknown>> | undefined) ?? []
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No entity relationships yet"
        description="Relationships populate as the knowledge graph learns from org usage."
      />
    )
  }
  return (
    <ul className="divide-y divide-divide border border-divide text-sm">
      {rows.slice(0, 20).map((row, index) => (
        <li key={String(row.id ?? index)} className="px-3 py-2">
          <span className="font-medium">{readString(row.source_entity_type, "entity")}</span> →{" "}
          <span className="font-medium">{readString(row.target_entity_type, "entity")}</span>
          <span className="ml-2 text-muted-foreground">{readString(row.relationship_type, "")}</span>
        </li>
      ))}
    </ul>
  )
}

export default function IntelligenceMemoryPage() {
  const { user } = useAuth()
  const [lens, setLens] = useState<MemoryLens>("org")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Always load KPI feeds when signed in so the metric strip stays honest across lenses.
  const { data: candidatesData, error, mutate } = useSWR(
    user ? "intelligence/memory/candidates" : null,
    () => memoryPromotionApi.candidates({ status: "pending", limit: 50 }),
  )
  const { data: auditData, mutate: mutateAudit } = useSWR(user ? "intelligence/memory/audit" : null, () =>
    memoryPromotionApi.audit({ limit: 50 }),
  )
  const { data: autoData } = useSWR(user ? "intelligence/memory/auto" : null, () =>
    memoryPromotionApi.recentAutoPromotions({ limit: 25 }),
  )

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to explore org memory." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load memory data"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const candidates = candidatesData?.items ?? []
  const auditItems = (auditData?.items as Array<Record<string, unknown>> | undefined) ?? []
  const autoItems = autoData?.items ?? []
  const selectedCandidate = candidates.find((row) => row.id === selectedId) ?? null
  const selectedAuto =
    autoItems.find((row, index) => String(row.memory_id ?? index) === selectedId) ?? null
  const selectedAudit = selectedCandidate
    ? auditItems.find((row) => row.candidate_id === selectedCandidate.id)
    : null

  async function handleRollback(memoryId: string) {
    try {
      await memoryPromotionApi.rollback(memoryId, "Rollback from Intelligence memory explorer")
      toast.success("Memory rolled back")
      setSelectedId(null)
      await Promise.all([mutate(), mutateAudit()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rollback failed")
    }
  }

  return (
    <AppShell title={copy.title}>
      <div>
        <GravitrePageHeader
          eyebrow="Intelligence"
          title={copy.title}
          description={copy.description}
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href={APP_ROUTES.learning}>{copy.autoAdminLink}</Link>
            </Button>
          }
        />

        <div className="space-y-6 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <section className="grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Pending promotions"
              value={candidates.length}
              hint="Select a memory — inspector stays closed until then."
              warning={candidates.length > 0}
            />
            <GravitreMetric
              label="Auto-promotions"
              value={autoItems.length}
              hint="Recent automatic promotions"
            />
            <GravitreMetric
              label="Audit events"
              value={auditItems.length}
              hint="Loaded trail (newest first)"
            />
          </section>

          <SegmentedControl
            ariaLabel="Memory view"
            options={LENSES}
            value={lens}
            onChange={(next) => {
              setLens(next)
              setSelectedId(null)
            }}
          />

          {lens === "org" ? (
            candidates.length === 0 ? (
              <EmptyState
                iconSlot={<Brain className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
                title="No pending promotion candidates"
                description="Promoted memories appear here when the engine detects recurring org-wide patterns."
              />
            ) : (
              <div className="flex flex-col border border-divide lg:flex-row">
                <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="memory-queue">
                  {candidates.map((candidate) => {
                    const isSelected = selectedId === candidate.id
                    return (
                      <li key={candidate.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(candidate.id)}
                          className={cn(
                            "flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left",
                            isSelected
                              ? "bg-[color:var(--g-surface-2)]"
                              : "hover:bg-[color:var(--g-surface-2)]/50",
                          )}
                        >
                          <span className="min-w-0">
                            <span className="line-clamp-2 block text-sm font-medium text-foreground">
                              {candidate.content ?? "—"}
                            </span>
                            <span className={cn(TYPE.meta, "mt-0.5 block")}>
                              {candidate.source_table ?? "unknown"}
                              {candidate.updated_at
                                ? ` · ${formatDistanceToNow(new Date(candidate.updated_at), { addSuffix: true })}`
                                : ""}
                            </span>
                          </span>
                          <MemoryCategoryChip category={candidate.memory_category} size="sm" />
                        </button>
                      </li>
                    )
                  })}
                </ul>
                {selectedCandidate ? (
                  <div
                    className="flex-1 space-y-3 border-t border-divide p-4 lg:border-t-0 lg:border-l"
                    data-review-surface="memory-inspect"
                  >
                    <MemoryCategoryChip category={selectedCandidate.memory_category} size="md" />
                    <p className="text-sm leading-relaxed text-foreground text-pretty">
                      {selectedCandidate.content ?? "—"}
                    </p>
                    <p className={TYPE.meta}>
                      Source: {selectedCandidate.source_table ?? "unknown"} · Freshness:{" "}
                      {selectedCandidate.updated_at
                        ? formatDistanceToNow(new Date(selectedCandidate.updated_at), { addSuffix: true })
                        : "—"}
                    </p>
                    <div>
                      <p className={TYPE.eyebrow}>Why this was remembered</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {plainDecisionReasoning(
                          selectedAudit?.decision_reasoning ??
                            selectedAudit?.decisionReasoning ??
                            selectedCandidate.metadata,
                        )}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            )
          ) : null}

          {lens === "auto" ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">{copy.autoHint}</p>
              {autoItems.length === 0 ? (
                <EmptyState
                  title="No recent auto-promotions"
                  description="Auto-promotions appear when thresholds are met."
                />
              ) : (
                <div className="flex flex-col border border-divide lg:flex-row">
                  <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="memory-queue">
                    {autoItems.map((item, index) => {
                      const id = String(item.memory_id ?? index)
                      const isSelected = selectedId === id
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            onClick={() => setSelectedId(id)}
                            className={cn(
                              "w-full px-3 py-2.5 text-left",
                              isSelected
                                ? "bg-[color:var(--g-surface-2)]"
                                : "hover:bg-[color:var(--g-surface-2)]/50",
                            )}
                          >
                            <span className="line-clamp-2 block text-sm text-foreground">
                              {plainDecisionReasoning(item.decisionReasoning ?? item)}
                            </span>
                            <span className={cn(TYPE.meta, "mt-0.5 block")}>
                              {item.decided_at
                                ? formatDistanceToNow(new Date(String(item.decided_at)), { addSuffix: true })
                                : "Recently"}
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                  {selectedAuto ? (
                    <div
                      className="flex-1 space-y-3 border-t border-divide p-4 lg:border-t-0 lg:border-l"
                      data-review-surface="memory-inspect"
                    >
                      <p className="text-sm text-foreground">
                        {plainDecisionReasoning(selectedAuto.decisionReasoning ?? selectedAuto)}
                      </p>
                      <p className={TYPE.meta}>
                        {selectedAuto.decided_at
                          ? formatDistanceToNow(new Date(String(selectedAuto.decided_at)), { addSuffix: true })
                          : "Recently"}
                      </p>
                      {selectedAuto.memory_id ? (
                        <Button
                          size="sm"
                          data-review-cta="rollback"
                          onClick={() => handleRollback(String(selectedAuto.memory_id))}
                        >
                          <ArrowCounterClockwise className="mr-2 h-4 w-4" aria-hidden />
                          Rollback
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}

          {lens === "graph" ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground text-pretty">{copy.graphHint}</p>
              <RelationshipsLens />
              {auditItems.length > 0 ? (
                <ul className="divide-y divide-divide border border-divide text-sm">
                  {auditItems.slice(0, 10).map((row, index) => (
                    <li key={String(row.id ?? index)} className="px-3 py-2">
                      <span className="font-medium">{readString(row.entity_type, "memory")}</span> ·{" "}
                      {plainDecisionReasoning(row.decision_reasoning ?? row.decisionReasoning)}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
