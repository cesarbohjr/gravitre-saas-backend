"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { fetcher, apiFetch, formatUnknownError } from "@/lib/fetcher"
import type { MemoryPromotionData, PromotionCandidate } from "@/lib/admin-intelligence"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowFatUp, Brain, CheckCircle, Lightning, Sparkle } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, ScoreBar, formatPercent } from "./shared"

function scopeLabel(scope: string): string {
  return scope === "org" ? "Org-wide" : "Agent-only"
}

function CandidateRow({
  candidate,
  threshold,
  onAction,
  pending,
}: {
  candidate: PromotionCandidate
  threshold: number
  onAction: (id: string, action: "promote" | "reject") => void
  pending: boolean
}) {
  const eligibleForAuto = candidate.confidence >= threshold
  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="capitalize">{candidate.category}</Badge>
        <Badge variant="outline">{scopeLabel(candidate.suggestedScope)}</Badge>
        {candidate.agentName ? (
          <span className="text-xs text-muted-foreground">from {candidate.agentName}</span>
        ) : null}
        {eligibleForAuto ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
            <Lightning className="h-3.5 w-3.5" weight="duotone" aria-hidden />
            Auto-eligible
          </span>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          used {candidate.usageCount}×
        </span>
      </div>

      <p className="mt-2 text-sm leading-relaxed text-foreground text-pretty">{candidate.content}</p>
      {candidate.reason ? (
        <p className="mt-1 text-xs text-muted-foreground text-pretty">Why: {candidate.reason}</p>
      ) : null}

      <div className="mt-3 max-w-xs">
        <ScoreBar label="Generalization confidence" score={candidate.confidence} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" onClick={() => onAction(candidate.id, "promote")} disabled={pending}>
          <ArrowFatUp className="mr-1 h-4 w-4" weight="duotone" aria-hidden />
          Promote
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(candidate.id, "reject")} disabled={pending}>
          Dismiss
        </Button>
      </div>
    </li>
  )
}

export function MemoryPromotionTab({ active }: { active: boolean }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR<MemoryPromotionData>(
    active ? "/api/admin/intelligence/memory-promotion" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const [pendingId, setPendingId] = useState<string | null>(null)

  async function handleAction(id: string, action: "promote" | "reject") {
    setPendingId(id)
    try {
      const res = await apiFetch(`/api/admin/intelligence/memory-promotion/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        throw new Error(formatUnknownError(payload, `Request failed (${res.status})`))
      }
      toast.success(action === "promote" ? "Memory promoted" : "Candidate dismissed")
      await mutate()
    } catch (err) {
      toast.error(formatUnknownError(err, "Action failed"))
    } finally {
      setPendingId(null)
    }
  }

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex items-center gap-2 text-sm">
            <span
              className={
                data?.autoPromotionEnabled
                  ? "inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700"
                  : "inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-muted-foreground"
              }
            >
              <Lightning className="h-3.5 w-3.5" weight="duotone" aria-hidden />
              Auto-promotion {data?.autoPromotionEnabled ? "on" : "off"}
            </span>
            {data ? (
              <span className="text-xs text-muted-foreground">
                threshold {formatPercent(data.autoPromotionThreshold)} confidence
              </span>
            ) : null}
          </div>
          <DataFreshness
            updatedAt={data?.generatedAt ?? undefined}
            isRefreshing={isValidating}
            onRefresh={() => mutate()}
          />
        </div>

        <SectionCard
          title="Promotion candidates"
          description="Agent memories the engine thinks are useful beyond a single agent. Promote to share org-wide, or dismiss."
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.candidates.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.candidates.map((c) => (
                <CandidateRow
                  key={c.id}
                  candidate={c}
                  threshold={data.autoPromotionThreshold}
                  onAction={handleAction}
                  pending={pendingId === c.id}
                />
              ))}
            </ul>
          ) : (
            <NotYetPopulated>
              No candidates right now. As agents accumulate memories that prove useful across tasks,
              the engine will surface the ones worth sharing org-wide here.
            </NotYetPopulated>
          )}
        </SectionCard>

        <SectionCard
          title="Recently promoted"
          description="Memories now shared across the organization."
          icon={<CheckCircle className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {data && data.promoted.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.promoted.map((m) => (
                <li key={m.id} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="text-sm text-foreground text-pretty">{m.content}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {new Date(m.promotedAt).toLocaleDateString()} · {scopeLabel(m.scope)}
                      {m.agentName ? ` · from ${m.agentName}` : ""}
                    </p>
                  </div>
                  <Badge
                    variant="secondary"
                    className="shrink-0 inline-flex items-center gap-1"
                  >
                    {m.promotedBy === "auto" ? (
                      <Sparkle className="h-3 w-3" weight="duotone" aria-hidden />
                    ) : null}
                    {m.promotedBy === "auto" ? "Auto" : "Manual"}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <NotYetPopulated>Nothing promoted yet. Promoted memories will be listed here.</NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
