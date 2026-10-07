"use client"

/**
 * Knowledge › Memory: how a memory is earned, the review queue and the
 * inspector. Everything is read from and written to the memory-promotion admin
 * API (candidates, approve, reject, recent auto-promotions, rollback, audit).
 * The only made-up content is the design's example memory, shown only while
 * "Preview with an example memory" is on and always badged "Example".
 */
import { useEffect, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { ArrowCounterClockwise, Brain, Sparkle } from "@phosphor-icons/react"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/fetcher"
import { memoryPromotionApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { MemoryPipeline } from "@/components/intelligence/knowledge/memory-pipeline"
import {
  KNOWLEDGE_CARD,
  KNOWLEDGE_STAT,
  KNOWLEDGE_TILE,
} from "@/components/intelligence/knowledge/knowledge-card"
import {
  EXAMPLE_MEMORY,
  memoryScopeLabel,
  seenLabel,
  type MemoryItem,
  type MemoryQueueFilter,
} from "@/components/intelligence/knowledge/memory-model"
import type { useOrgMemory } from "@/components/intelligence/knowledge/use-org-memory"

type OrgMemory = ReturnType<typeof useOrgMemory>

const FILTERS: { id: MemoryQueueFilter; label: string }[] = [
  { id: "pending", label: "Pending" },
  { id: "auto", label: "Auto" },
  { id: "rejected", label: "Rejected" },
]

const SOURCE_DOT: Record<string, string> = {
  source: "bg-[color:var(--g-electric)]",
  observed: "bg-[color:var(--g-approval)]",
  decided: "bg-[color:var(--g-brand)]",
}

const SOURCE_ROLE_LABEL: Record<string, string> = {
  source: "source",
  observed: "observed",
  decided: "decided",
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <span className="flex w-full items-center gap-2.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[color:var(--g-surface-3)]">
        <span className="block h-full bg-[color:var(--g-brand-active)]" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      <span className="font-mono text-xs tabular-nums text-[color:var(--g-text-primary)]">{value.toFixed(2)}</span>
    </span>
  )
}

function QueueCard({ item, selected, onSelect }: { item: MemoryItem; selected: boolean; onSelect: () => void }) {
  const seen = seenLabel(item)
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        KNOWLEDGE_TILE,
        "flex w-full flex-col gap-2.5 border bg-[color:var(--g-surface-1)] p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
        selected
          ? "border-[color:var(--g-brand-active)] ring-4 ring-[color:var(--g-brand-soft)]"
          : "border-divide hover:border-[color:var(--g-border-strong)]",
      )}
    >
      <span className="flex w-full items-center justify-between gap-2">
        {item.kind === "example" ? (
          <span className="rounded-[5px] bg-[color:var(--g-surface-2)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-[color:var(--g-text-secondary)]">
            Example
          </span>
        ) : (
          <span className={TYPE.meta}>{item.sources[0]?.label}</span>
        )}
        {seen ? <span className={TYPE.meta}>{seen}</span> : null}
      </span>
      <span className="text-sm leading-relaxed text-[color:var(--g-text-primary)]">{item.content}</span>
      {item.confidence != null ? <ConfidenceBar value={item.confidence} /> : null}
    </button>
  )
}

function QueueEmpty({ filter, memory }: { filter: MemoryQueueFilter; memory: OrgMemory }) {
  if (filter !== "pending") {
    return (
      <div className="rounded-[14px] border-[1.5px] border-dashed border-[color:var(--g-border-default)] px-5 py-7 text-center">
        <p className={TYPE.bodyMuted}>
          {filter === "auto"
            ? "Nothing was shared automatically in the last 30 days."
            : "Nothing rejected yet. Rejected memories stay here so Gravitre does not suggest them again."}
        </p>
      </div>
    )
  }
  const running = memory.runningAgents.length > 0
  const target = memory.watchedAgents.find((a) => a.status !== "processing") ?? memory.watchedAgents[0] ?? null
  return (
    <div className="flex flex-col items-center gap-2.5 rounded-[14px] border-[1.5px] border-dashed border-[color:var(--g-border-default)] px-5 py-7 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-[12px] bg-[color:var(--g-surface-2)]">
        <Brain className="h-5 w-5 text-[color:var(--g-text-secondary)]" aria-hidden />
      </span>
      <strong className="text-sm font-semibold text-[color:var(--g-text-primary)]">No real candidates yet</strong>
      <span className="max-w-[340px] text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">
        They appear here once an agent sees the same fact across several runs.{" "}
        {!memory.agentsLoaded
          ? null
          : running
            ? "An agent is running now, so check back soon."
            : target
              ? memory.watchedAgents.length === 1
                ? "Your agent is idle, so start a run to begin."
                : "Your agents are idle, so start a run to begin."
              : "Create an agent and run it to begin."}
      </span>
      {memory.agentsLoaded ? (
        target ? (
          <Link
            href={`${APP_ROUTES.agents}/${encodeURIComponent(target.id)}`}
            className="text-[13px] font-medium text-[color:var(--g-brand-active)] underline underline-offset-2"
          >
            Run {target.name} →
          </Link>
        ) : (
          <Link
            href={`${APP_ROUTES.agents}/new`}
            className="text-[13px] font-medium text-[color:var(--g-brand-active)] underline underline-offset-2"
          >
            Create an agent →
          </Link>
        )
      ) : null}
    </div>
  )
}

function StatTile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1 bg-[color:var(--g-surface-2)] p-3", KNOWLEDGE_STAT)}>
      <span className={TYPE.meta}>{label}</span>
      <span
        className={cn(
          "truncate text-lg font-semibold",
          accent ? "text-[color:var(--g-electric)]" : "text-[color:var(--g-text-primary)]",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  )
}

function impactNote(item: MemoryItem): string {
  if (item.kind === "example" && item.note) return item.note
  const parts: string[] = []
  if (item.kind === "pending") {
    const scope = memoryScopeLabel(item)
    parts.push(
      scope === "Not set"
        ? "If approved, Gravitre writes this to the memory of the agents it applies to."
        : `If approved, every agent in ${scope === "Whole org" ? "your organization" : scope.toLowerCase().endsWith("teams") ? `those ${scope}` : `the ${scope}`} uses this in its runs and answers.`,
    )
  } else if (item.kind === "auto") {
    parts.push("Gravitre shared this automatically. Roll it back to remove it from every agent that received it.")
  } else if (item.kind === "rejected") {
    parts.push("Rejected. Gravitre will not suggest this memory again.")
  }
  if (item.frequency != null && item.minOccurrences != null && item.minDepartments != null && item.kind === "pending") {
    parts.push(
      `Seen ${item.frequency} of ${item.minOccurrences} times across ${item.departmentCount ?? 0} of ${item.minDepartments} teams needed to share it automatically.`,
    )
  }
  if (item.note && item.kind !== "pending") parts.push(item.note)
  return parts.join(" ")
}

export function OrgMemorySection({ memory, previewExample }: { memory: OrgMemory; previewExample: boolean }) {
  const [filter, setFilter] = useState<MemoryQueueFilter>("pending")
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [busy, setBusy] = useState<"approve" | "reject" | "rollback" | null>(null)

  // Turning the preview on shows the example in the inspector, as the design does.
  useEffect(() => {
    if (previewExample) {
      setFilter("pending")
      setSelectedKey(EXAMPLE_MEMORY.key)
    } else {
      setSelectedKey((key) => (key === EXAMPLE_MEMORY.key ? null : key))
    }
  }, [previewExample])

  if (memory.error) {
    return (
      <ErrorState
        title="Unable to load memory data"
        description={memory.error instanceof ApiError ? memory.error.message : "Please try again."}
        onRetry={() => void memory.refresh()}
      />
    )
  }

  const realItems = memory.queues[filter]
  const items = previewExample && filter === "pending" ? [EXAMPLE_MEMORY, ...realItems] : realItems
  // Like the design, the inspector shows the first memory in the queue until another is picked.
  const selectedCandidate = items.find((item) => item.key === selectedKey) ?? items[0] ?? null
  const isExample = selectedCandidate?.kind === "example"

  async function run(action: "approve" | "reject" | "rollback", item: MemoryItem) {
    setBusy(action)
    try {
      if (action === "approve" && item.candidateId) {
        await memoryPromotionApi.approve(item.candidateId)
        toast.success("Memory approved for your whole organization")
      } else if (action === "reject" && item.candidateId) {
        await memoryPromotionApi.reject(item.candidateId, "Rejected from Knowledge › Memory")
        toast.success("Memory rejected")
      } else if (action === "rollback" && item.memoryId) {
        await memoryPromotionApi.rollback(item.memoryId, "Rolled back from Knowledge › Memory")
        toast.success("Memory rolled back")
      }
      setSelectedKey(null)
      await memory.refresh()
    } catch (err) {
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "That didn't work. Try again.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      <MemoryPipeline
        pipeline={memory.pipeline}
        policy={memory.policy}
        watchedAgents={memory.watchedAgents.length}
        agentsLoaded={memory.agentsLoaded}
      />

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section
          aria-labelledby="memory-queue-heading"
          className={cn(KNOWLEDGE_CARD, "space-y-4 p-5 sm:p-[22px]")}
          data-review-surface="memory-queue"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="memory-queue-heading" className={TYPE.cardTitle}>
              Review queue
            </h2>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter the review queue">
              {FILTERS.map((f) => {
                const active = filter === f.id
                return (
                  <button
                    key={f.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setFilter(f.id)
                      setSelectedKey(previewExample && f.id === "pending" ? EXAMPLE_MEMORY.key : null)
                    }}
                    className={cn(
                      "min-h-8 rounded-full px-3 text-xs tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
                      active
                        ? "bg-foreground text-background"
                        : "border border-divide bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)] hover:bg-[color:var(--g-surface-3)]",
                    )}
                  >
                    {f.label} {memory.isLoading ? "—" : memory.queues[f.id].length}
                  </button>
                )
              })}
            </div>
          </div>

          {memory.isLoading && !previewExample ? (
            <p className={TYPE.bodyMuted}>Loading memory candidates…</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {items.map((item) => (
                <li key={item.key}>
                  <QueueCard
                    item={item}
                    selected={selectedCandidate?.key === item.key}
                    onSelect={() => setSelectedKey(item.key)}
                  />
                </li>
              ))}
              {realItems.length === 0 && !memory.isLoading ? (
                <li>
                  <QueueEmpty filter={filter} memory={memory} />
                </li>
              ) : null}
            </ul>
          )}
        </section>

        <section
          aria-labelledby="memory-inspector-heading"
          className={cn(KNOWLEDGE_CARD, "space-y-[18px] p-5 sm:p-[22px]")}
          data-review-surface="memory-inspect"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 id="memory-inspector-heading" className={TYPE.cardTitle}>
              Inspector
            </h2>
            {selectedCandidate ? (
              <span className={TYPE.meta}>
                {isExample
                  ? "Example memory"
                  : selectedCandidate.kind === "auto"
                    ? "Shared automatically"
                    : selectedCandidate.kind === "rejected"
                      ? "Rejected"
                      : "Waiting for review"}
              </span>
            ) : null}
          </div>

          {selectedCandidate ? (
            <>
              <blockquote className="text-lg font-medium leading-snug tracking-[-0.01em] text-[color:var(--g-text-primary)]">
                “{selectedCandidate.content}”
              </blockquote>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                <StatTile
                  label="Confidence"
                  value={selectedCandidate.confidence != null ? selectedCandidate.confidence.toFixed(2) : "Not scored yet"}
                />
                <StatTile label="Scope" value={memoryScopeLabel(selectedCandidate)} />
                <StatTile label="Links to" value={selectedCandidate.linksTo ?? "—"} accent={Boolean(selectedCandidate.linksTo)} />
              </div>

              <div className="space-y-2.5">
                <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]">
                  Where it came from
                </span>
                <ol className="divide-y divide-divide">
                  {selectedCandidate.sources.map((row, index) => (
                    <li
                      key={`${row.label}-${index}`}
                      className="grid grid-cols-[20px_minmax(0,1fr)_auto] gap-3 py-2.5 text-[13px] text-[color:var(--g-text-primary)]"
                    >
                      <span aria-hidden className={cn("mt-[5px] ml-1.5 h-2 w-2 rounded-full", SOURCE_DOT[row.role])} />
                      <span className="min-w-0">{row.label}</span>
                      <span className="font-mono text-xs text-[color:var(--g-text-muted)]">{SOURCE_ROLE_LABEL[row.role]}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="flex items-start gap-2.5 rounded-[12px] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] px-3.5 py-3">
                <Sparkle className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--g-brand-active)]" aria-hidden />
                <span className="text-[13px] leading-relaxed text-[color:var(--g-text-primary)]">
                  {impactNote(selectedCandidate)}
                </span>
              </div>

              {selectedCandidate.kind === "auto" ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    className="min-h-11 flex-1 basis-[140px]"
                    data-review-cta="rollback"
                    disabled={!selectedCandidate.memoryId || busy !== null}
                    title={selectedCandidate.memoryId ? undefined : "This decision has no memory to roll back."}
                    onClick={() => void run("rollback", selectedCandidate)}
                  >
                    <ArrowCounterClockwise className="mr-2 h-4 w-4" aria-hidden />
                    {busy === "rollback" ? "Rolling back…" : "Roll back"}
                  </Button>
                </div>
              ) : selectedCandidate.kind === "rejected" ? null : (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="brand"
                    className="min-h-11 flex-1 basis-[140px]"
                    data-review-cta="approve"
                    disabled={isExample || busy !== null}
                    title={isExample ? "This is an example. There is nothing to approve." : undefined}
                    onClick={() => void run("approve", selectedCandidate)}
                  >
                    {busy === "approve" ? "Approving…" : "Approve for org"}
                  </Button>
                  <Button
                    variant="outline"
                    className="min-h-11 flex-1 basis-[100px]"
                    disabled
                    title="Editing a memory before approval is not supported yet."
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    className="min-h-11 flex-1 basis-[100px] text-[color:var(--g-danger)]"
                    data-review-cta="reject"
                    disabled={isExample || busy !== null}
                    title={isExample ? "This is an example. There is nothing to reject." : undefined}
                    onClick={() => void run("reject", selectedCandidate)}
                  >
                    {busy === "reject" ? "Rejecting…" : "Reject"}
                  </Button>
                </div>
              )}
            </>
          ) : (
            <p className={TYPE.bodyMuted}>
              Pick a memory from the review queue to see where it came from. The inspector stays closed until then.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
