"use client"

/**
 * Organization memory, shown as a section of Intelligence › Knowledge.
 * This used to be its own page (/intelligence/memory) with pill tabs and a
 * second copy of the knowledge graph; the graph now lives only in Knowledge's
 * Relationships section and this keeps the two lists stacked.
 */
import { useState } from "react"
import useSWR from "swr"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { Brain, ArrowCounterClockwise } from "@phosphor-icons/react"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { memoryPromotionApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { plainDecisionReasoning, readString } from "@/lib/intelligence/helpers"
import { MemoryCategoryChip } from "@/components/intelligence/memory-category-chip"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

const copy = SURFACE_COPY.pages.memory

export function OrgMemorySection({ enabled }: { enabled: boolean }) {
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [selectedAutoId, setSelectedAutoId] = useState<string | null>(null)

  const { data: candidatesData, error, mutate } = useSWR(
    enabled ? "intelligence/memory/candidates" : null,
    () => memoryPromotionApi.candidates({ status: "pending", limit: 50 }),
  )
  const { data: auditData, mutate: mutateAudit } = useSWR(enabled ? "intelligence/memory/audit" : null, () =>
    memoryPromotionApi.audit({ limit: 50 }),
  )
  const { data: autoData } = useSWR(enabled ? "intelligence/memory/auto" : null, () =>
    memoryPromotionApi.recentAutoPromotions({ limit: 25 }),
  )

  if (error) {
    return (
      <ErrorState
        title="Unable to load memory data"
        description={error instanceof ApiError ? error.message : "Please try again."}
        onRetry={() => mutate()}
      />
    )
  }

  const candidates = candidatesData?.items ?? []
  const auditItems = (auditData?.items as Array<Record<string, unknown>> | undefined) ?? []
  const autoItems = autoData?.items ?? []
  const selectedCandidate = candidates.find((row) => row.id === selectedCandidateId) ?? null
  const selectedAuto =
    autoItems.find((row, index) => String(row.memory_id ?? index) === selectedAutoId) ?? null
  const selectedAudit = selectedCandidate
    ? auditItems.find((row) => row.candidate_id === selectedCandidate.id)
    : null

  async function handleRollback(memoryId: string) {
    try {
      await memoryPromotionApi.rollback(memoryId, "Rollback from Intelligence memory explorer")
      toast.success("Memory rolled back")
      setSelectedAutoId(null)
      await Promise.all([mutate(), mutateAudit()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rollback failed")
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
        <GravitreMetric
          label="Pending promotions"
          value={candidates.length}
          hint="Select a memory — inspector stays closed until then."
          warning={candidates.length > 0}
        />
        <GravitreMetric label="Auto-promotions" value={autoItems.length} hint="Recent automatic promotions" />
        <GravitreMetric label="Audit events" value={auditItems.length} hint="Loaded trail (newest first)" />
      </section>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">{copy.tabPromoted}</h3>
        {candidates.length === 0 ? (
              <EmptyState
                iconSlot={<Brain className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
                title="No pending promotion candidates"
                description="Promoted memories appear here when the engine detects recurring org-wide patterns."
              />
            ) : (
              <div className="flex flex-col border border-divide lg:flex-row">
                <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="memory-queue">
                  {candidates.map((candidate) => {
                    const isSelected = selectedCandidateId === candidate.id
                    return (
                      <li key={candidate.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedCandidateId(candidate.id)}
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
        )}
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground">{copy.tabAuto}</h3>
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
                      const isSelected = selectedAutoId === id
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            onClick={() => setSelectedAutoId(id)}
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
      </div>

      {auditItems.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-foreground">Recent decisions</h3>
          <ul className="divide-y divide-divide border border-divide text-sm">
            {auditItems.slice(0, 10).map((row, index) => (
              <li key={String(row.id ?? index)} className="px-3 py-2">
                <span className="font-medium">{readString(row.entity_type, "memory")}</span> ·{" "}
                {plainDecisionReasoning(row.decision_reasoning ?? row.decisionReasoning)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
