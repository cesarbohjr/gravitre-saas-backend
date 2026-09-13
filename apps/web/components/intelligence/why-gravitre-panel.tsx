"use client"

/**
 * Intelligence redesign, Phase 4 + Phase D corrective — "Why Gravitre thinks this."
 *
 * Visual evidence graph (insight → signals → sources) backed by real provenance from
 * `department_signal_scoring_service.score_all_departments()`. Accordion list replaced
 * in Phase D — same data, graph-first presentation.
 */

import useSWR from "swr"
import { useMemo, useState } from "react"
import { assistantApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { EvidenceGraphCanvas, EvidenceGraphMeta } from "./evidence-graph-canvas"
import { buildEvidenceGraph } from "./evidence-graph-topology"

export type SourceStatus = "live_connector" | "knowledge_fabric_only" | "missing"

export type SignalEvidence = {
  sourceId?: string
  sourceLabel?: string
  status?: SourceStatus
  eventHits?: number
  externalSignalHits?: number
  strength?: number
}

export type SignalContribution = {
  signalId?: string
  label?: string
  weight?: number
  signalScore?: number
  points?: number
  description?: string
  evidence?: SignalEvidence[]
}

export type PriorityItem = {
  workObjectId?: string
  title?: string
  department?: string
  priorityScore?: number
  priorityBand?: string
  signalContributions?: SignalContribution[]
  explanations?: string[]
  gaps?: string[]
}

export type DepartmentScorePayload = {
  department?: string
  capturedAt?: string
  priorities?: PriorityItem[]
  gaps?: string[]
}

export type AllDepartmentsPayload = {
  capturedAt?: string
  departments?: DepartmentScorePayload[]
}

const MAX_ITEMS = 4

export function flattenPriorities(
  data: AllDepartmentsPayload | null | undefined,
  maxItems: number = MAX_ITEMS,
): PriorityItem[] {
  const departments = data?.departments ?? []
  return departments
    .flatMap((dept) =>
      (dept.priorities ?? []).map((item) => ({
        ...item,
        department: item.department ?? dept.department,
      })),
    )
    .sort((a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0))
    .slice(0, maxItems)
}

export function collectDepartmentGaps(
  data: AllDepartmentsPayload | null | undefined,
  maxGaps: number = 3,
): string[] {
  const departments = data?.departments ?? []
  return departments.flatMap((dept) => dept.gaps ?? []).slice(0, maxGaps)
}

export function useWhyGravitreEvidence(enabled: boolean) {
  return useSWR(
    enabled ? "intelligence/overview/why-evidence" : null,
    () => assistantApi.businessSignalPriorities({ limit: 3 }) as Promise<AllDepartmentsPayload>,
    { revalidateOnFocus: false },
  )
}

export function sourceStatusLabel(status: SourceStatus | undefined): string {
  switch (status) {
    case "live_connector":
      return "Connected source"
    case "knowledge_fabric_only":
      return "Knowledge only, not connected"
    case "missing":
      return "No source available"
    default:
      return "Unknown source state"
  }
}

export function relativeFreshness(iso: string | undefined, now: number = Date.now()): string {
  if (!iso) return "Freshness not available"
  const parsed = Date.parse(iso)
  if (Number.isNaN(parsed)) return "Freshness not available"
  const diffMs = now - parsed
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return "Evidence captured just now"
  if (minutes < 60) return `Evidence captured ${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `Evidence captured ${hours}h ago`
  const days = Math.round(hours / 24)
  return `Evidence captured ${days}d ago`
}

export function evidenceEventCount(evidence: SignalEvidence): number {
  return (evidence.eventHits ?? 0) + (evidence.externalSignalHits ?? 0)
}

function priorityBandTone(band: string | undefined): string {
  switch (band) {
    case "critical":
      return "text-[color:var(--g-approval-bright)]"
    case "high":
      return "text-[color:var(--g-brand)]"
    case "medium":
      return "text-amber-600 dark:text-amber-400"
    default:
      return "text-[color:var(--g-text-muted)]"
  }
}

export function WhyGravitrePanel({
  data,
  isLoading,
  className,
}: {
  data: AllDepartmentsPayload | null | undefined
  isLoading?: boolean
  className?: string
}) {
  const top = flattenPriorities(data)
  const departmentGaps = collectDepartmentGaps(data)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const activeId = selectedId ?? top[0]?.workObjectId ?? top[0]?.title ?? null
  const activeItem = top.find((item) => (item.workObjectId ?? item.title) === activeId) ?? top[0]

  const graphMeta = useMemo(
    () => (activeItem ? buildEvidenceGraph(activeItem).meta : null),
    [activeItem],
  )

  return (
    <section
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="why-gravitre-heading"
      data-why-gravitre-panel=""
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Evidence</p>
          <h2 id="why-gravitre-heading" className={TYPE.sectionTitle}>
            Why Gravitre thinks this
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
            Visual evidence graph — insight at the center, contributing signals branching out,
            sources at the leaves. Honest gaps shown when a source isn&apos;t connected yet.
          </p>
        </div>
        {data?.capturedAt ? (
          <p className={cn(TYPE.meta, "shrink-0")}>{relativeFreshness(data.capturedAt)}</p>
        ) : null}
      </div>

      {isLoading && !data ? (
        <p className={cn(TYPE.meta, "mt-4")}>Loading evidence…</p>
      ) : top.length === 0 ? (
        <div className="mt-4 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-6 text-center">
          <p className={TYPE.cardTitle}>No scored priorities yet</p>
          <p className={cn(TYPE.meta, "mt-1")}>
            {departmentGaps[0] ??
              "No department has enough recent activity to produce a scored, evidence-backed priority yet."}
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {top.length > 1 ? (
            <div
              className="flex flex-wrap gap-2"
              role="tablist"
              aria-label="Select priority insight"
            >
              {top.map((item) => {
                const id = item.workObjectId ?? item.title ?? ""
                const active = id === activeId
                return (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setSelectedId(id)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-left text-xs transition-colors",
                      active
                        ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)]"
                        : "border-divide bg-[color:var(--g-surface-2)] hover:border-[color:var(--g-brand-border)]",
                    )}
                  >
                    <span className="block font-medium">{item.title ?? "Priority"}</span>
                    <span className={cn("text-[10px] uppercase", priorityBandTone(item.priorityBand))}>
                      {item.priorityScore != null ? `${Math.round(item.priorityScore)}/100` : "—"}
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}

          {activeItem ? (
            <>
              <EvidenceGraphCanvas item={activeItem} />
              {graphMeta ? (
                <EvidenceGraphMeta
                  item={activeItem}
                  capturedAt={data?.capturedAt}
                  meta={graphMeta}
                />
              ) : null}
            </>
          ) : null}
        </div>
      )}
    </section>
  )
}
