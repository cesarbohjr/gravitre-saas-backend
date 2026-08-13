"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { memoryPromotionApi, type PromotionCandidate } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { memoryCategoryLabel } from "@/lib/learning-ui-copy"
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
import { ArrowFatUp, Brain, CheckCircle, Lightning } from "@phosphor-icons/react"
import { SectionCard, NotYetPopulated, TabStateGate, formatTime, readNumber } from "./shared"

const PAGE_SIZE = 15

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
  const category = memoryCategoryLabel(candidate.memory_category ?? candidate.candidate_type ?? "memory")
  const freq = readNumber(candidate.frequency, 0)
  const depts = readNumber(candidate.department_count, 0)
  const meets = tc?.meetsAutoThreshold ?? false

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{category}</Badge>
        {meets ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <Lightning className="h-3.5 w-3.5" weight="duotone" aria-hidden />
            Ready to promote automatically
          </span>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">seen {freq}×</span>
      </div>

      <p className="mt-2 text-sm leading-relaxed text-foreground text-pretty">{candidate.content ?? "—"}</p>

      {tc ? (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
          <span>
            Times seen {freq}/{tc.autoPromoteMinOccurrences}
          </span>
          <span>
            Teams {depts}/{tc.autoPromoteMinDepartments}
          </span>
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => onAction(candidate.id, "approve")} disabled={pending}>
          <ArrowFatUp className="mr-1 h-4 w-4" weight="duotone" aria-hidden />
          Share org-wide
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onAction(candidate.id, "reject")} disabled={pending}>
          Dismiss
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
    () => memoryPromotionApi.candidates({ status: "pending", limit: 100 }),
    { revalidateOnFocus: false },
  )
  const { data: recentData, mutate: mutateRecent } = useSWR(
    enabled ? ["admin/memory-promotion/recent-auto"] : null,
    () => memoryPromotionApi.recentAutoPromotions({ limit: 25 }),
    { revalidateOnFocus: false },
  )

  const [pendingId, setPendingId] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<"all" | "ready" | "needs_more">("all")
  const [page, setPage] = useState(0)

  const candidates = candidatesData?.items ?? []
  const recent = recentData?.items ?? []

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return candidates.filter((c) => {
      const meets = c.thresholdComparison?.meetsAutoThreshold ?? false
      if (filter === "ready" && !meets) return false
      if (filter === "needs_more" && meets) return false
      if (!q) return true
      const hay = `${c.content ?? ""} ${c.memory_category ?? ""} ${c.candidate_type ?? ""}`.toLowerCase()
      return hay.includes(q)
    })
  }, [candidates, filter, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

  async function handleAction(id: string, action: "approve" | "reject") {
    setPendingId(id)
    try {
      if (action === "approve") {
        await memoryPromotionApi.approve(id)
        toast.success("Memory shared across your organization")
      } else {
        await memoryPromotionApi.reject(id)
        toast.success("Candidate dismissed")
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
      <div className="space-y-6">
        <SectionCard
          title="Memories to share"
          description="When the same useful fact shows up across agents and teams, review it here. Approve to make it available org-wide, or dismiss."
          icon={<Brain className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          {candidates.length > 0 ? (
            <>
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Input
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setPage(0)
                  }}
                  placeholder="Search memory text…"
                  className="sm:max-w-xs"
                  aria-label="Search candidates"
                />
                <Select
                  value={filter}
                  onValueChange={(v) => {
                    setFilter(v as typeof filter)
                    setPage(0)
                  }}
                >
                  <SelectTrigger className="w-full sm:w-[11rem]" aria-label="Filter candidates">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All pending</SelectItem>
                    <SelectItem value="ready">Ready to auto-share</SelectItem>
                    <SelectItem value="needs_more">Still gathering signal</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground sm:ml-auto tabular-nums">
                  {filtered.length} of {candidates.length}
                </p>
              </div>
              {pageItems.length > 0 ? (
                <ul className="divide-y divide-border">
                  {pageItems.map((c) => (
                    <CandidateRow
                      key={c.id}
                      candidate={c}
                      onAction={handleAction}
                      pending={pendingId === c.id}
                    />
                  ))}
                </ul>
              ) : (
                <NotYetPopulated>No candidates match this filter.</NotYetPopulated>
              )}
              {pageCount > 1 ? (
                <div className="mt-4 flex items-center justify-between gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={safePage <= 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    Page {safePage + 1} of {pageCount}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={safePage >= pageCount - 1}
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              ) : null}
            </>
          ) : (
            <NotYetPopulated>
              Nothing waiting for review. As useful memories repeat across agents and teams, they show up here for
              sharing.
            </NotYetPopulated>
          )}
        </SectionCard>

        <SectionCard
          title="Recently shared automatically"
          description="Memories Gravitre shared after they met safe thresholds. Each keeps a rollback path if needed."
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
                      {m.decisionReasoning ?? m.promotionPath ?? "Shared memory"}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatTime(m.decided_at)}
                      {m.decided_by ? ` · ${m.decided_by}` : ""}
                    </p>
                  </div>
                  <Badge variant="secondary" className="shrink-0 capitalize">
                    {String(m.action ?? "shared").replace(/_/g, " ")}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <NotYetPopulated>No automatic shares yet. They will appear here once thresholds are met.</NotYetPopulated>
          )}
        </SectionCard>
      </div>
    </TabStateGate>
  )
}
