"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { memoryPromotionApi, type PromotionCandidate } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowFatUp, Brain, CheckCircle, Lightning } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, formatTime, readNumber } from "./shared"

function CandidateRow({
  candidate,
  onAction,
  pending,
}: {
  candidate: PromotionCandidate
  onAction: (id: string, action: "approve" | "reject") => void
  pending: boolean
}) {
  const tc = candidate.thresholdComparison
  const category = candidate.memory_category ?? candidate.candidate_type ?? "memory"
  const freq = readNumber(candidate.frequency, 0)
  const depts = readNumber(candidate.department_count, 0)
  const meets = tc?.meetsAutoThreshold ?? false

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="capitalize">{String(category)}</Badge>
        {candidate.source_table ? <Badge variant="outline">{candidate.source_table}</Badge> : null}
        {meets ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
            <Lightning className="h-3.5 w-3.5" weight="duotone" aria-hidden />
            Meets auto-threshold
          </span>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">seen {freq}×</span>
      </div>

      <p className="mt-2 text-sm leading-relaxed text-foreground text-pretty">{candidate.content ?? "—"}</p>

      {tc ? (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
          <span>
            occurrences {freq}/{tc.autoPromoteMinOccurrences}
          </span>
          <span>
            departments {depts}/{tc.autoPromoteMinDepartments}
          </span>
          {tc.canAutoPromote ? <span className="text-emerald-600">eligible for auto-promotion</span> : null}
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={() => onAction(candidate.id, "approve")} disabled={pending}>
          <ArrowFatUp className="mr-1 h-4 w-4" weight="duotone" aria-hidden />
          Approve
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(candidate.id, "reject")} disabled={pending}>
          Reject
        </Button>
      </div>
    </li>
  )
}

export function MemoryPromotionTab({ enabled }: { enabled: boolean }) {
  const {
    data: candidatesData,
    error,
    isLoading,
    mutate,
  } = useSWR(
    enabled ? ["admin/memory-promotion/candidates"] : null,
    () => memoryPromotionApi.candidates({ status: "pending", limit: 50 }),
    { revalidateOnFocus: false },
  )
  const { data: recentData, mutate: mutateRecent } = useSWR(
    enabled ? ["admin/memory-promotion/recent-auto"] : null,
    () => memoryPromotionApi.recentAutoPromotions({ limit: 25 }),
    { revalidateOnFocus: false },
  )

  const [pendingId, setPendingId] = useState<string | null>(null)
  const candidates = candidatesData?.items ?? []
  const recent = recentData?.items ?? []

  async function handleAction(id: string, action: "approve" | "reject") {
    setPendingId(id)
    try {
      if (action === "approve") {
        await memoryPromotionApi.approve(id)
        toast.success("Memory promoted org-wide")
      } else {
        await memoryPromotionApi.reject(id)
        toast.success("Candidate rejected")
      }
      await Promise.all([mutate(), mutateRecent()])
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed")
    } finally {
      setPendingId(null)
    }
  }

  return (
    <TabStateGate isLoading={isLoading && !candidatesData} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
        <SectionCard
          title="Promotion candidates"
          description="Agent memories the engine recurring across departments. Approve to share org-wide, or reject. Candidates meeting the occurrence and department thresholds are also eligible for automatic promotion."
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {candidates.length > 0 ? (
            <ul className="divide-y divide-border">
              {candidates.map((c) => (
                <CandidateRow key={c.id} candidate={c} onAction={handleAction} pending={pendingId === c.id} />
              ))}
            </ul>
          ) : (
            <NotYetPopulated>
              No pending candidates right now. As memories recur across agents and departments, the engine surfaces
              the ones worth sharing org-wide here.
            </NotYetPopulated>
          )}
        </SectionCard>

        <SectionCard
          title="Recent auto-promotions"
          description="Memories the engine promoted automatically after meeting the safety thresholds. Each keeps a rollback path."
          icon={<CheckCircle className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {recent.length > 0 ? (
            <ul className="divide-y divide-border">
              {recent.map((m, i) => (
                <li
                  key={String(m.memory_id ?? m.candidate_id ?? i)}
                  className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-foreground text-pretty">
                      {m.decisionReasoning ?? m.promotionPath ?? "Promoted memory"}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatTime(m.decided_at)}
                      {m.decided_by ? ` · ${m.decided_by}` : ""}
                      {m.source_table ? ` · ${m.source_table}` : ""}
                    </p>
                  </div>
                  <Badge variant="secondary" className="shrink-0">
                    {m.action ?? "promoted"}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <NotYetPopulated>No automatic promotions yet. Auto-promoted memories will be listed here.</NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
