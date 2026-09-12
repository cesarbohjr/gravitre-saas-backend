"use client"

/**
 * Intelligence redesign, Phase 4 (2026-09-11) — "Why Gravitre thinks this."
 *
 * Every field here is real, structured provenance from
 * `backend/app/services/department_signal_scoring_service.py`
 * `score_department()` / `score_all_departments()`:
 *   - contributing signals  -> `signalContributions[]` (label, weight, score, points)
 *   - sources / evidence    -> `signalContributions[].evidence[]` (sourceLabel, status,
 *                              eventHits, externalSignalHits, strength)
 *   - confidence score      -> `priorityScore` (0-100) + `priorityBand`
 *   - freshness timestamp   -> `capturedAt` (real ISO timestamp from this scoring pass)
 *   - honest gaps           -> backend-disclosed `gaps[]` (department-level and per-item)
 *
 * Nothing here is invented. Where the backend has no live source for a signal,
 * that shows as a real, disclosed gap ("no live source available"), never a
 * fabricated evidence count or score.
 */

import useSWR from "swr"
import { assistantApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { CaretDown, CheckCircle, Circle, WarningCircle } from "@phosphor-icons/react"
import { useState } from "react"

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

/**
 * Pure data-shaping step, extracted so it can be unit-tested without a DOM
 * (this repo's vitest runs in `environment: "node"`, no jsdom/testing-library
 * — see apps/web/vitest.config.ts). This is exactly the kind of arithmetic
 * that hid the earlier Improves-pillar 100x scaling bug, so it gets its own
 * real, executable assertions rather than only a source-code read.
 */
export function flattenPriorities(
  data: AllDepartmentsPayload | null | undefined,
  maxItems: number = MAX_ITEMS,
): PriorityItem[] {
  const departments = data?.departments ?? []
  return departments
    .flatMap((dept) => (dept.priorities ?? []).map((item) => ({ ...item, department: item.department ?? dept.department })))
    .sort((a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0))
    .slice(0, maxItems)
}

export function collectDepartmentGaps(data: AllDepartmentsPayload | null | undefined, maxGaps: number = 3): string[] {
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

function StatusIcon({ status }: { status: SourceStatus | undefined }) {
  if (status === "live_connector") {
    return <CheckCircle className="h-3.5 w-3.5 text-[color:var(--g-success)]" weight="duotone" aria-hidden />
  }
  if (status === "missing") {
    return <WarningCircle className="h-3.5 w-3.5 text-amber-500" weight="duotone" aria-hidden />
  }
  return <Circle className="h-3.5 w-3.5 text-[color:var(--g-text-muted)]" weight="duotone" aria-hidden />
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

function EvidenceRow({ evidence }: { evidence: SignalEvidence }) {
  const count = evidenceEventCount(evidence)
  return (
    <li className="flex items-center justify-between gap-2 py-0.5 text-[11px]">
      <span className="flex items-center gap-1.5 text-[color:var(--g-text-secondary)]">
        <StatusIcon status={evidence.status} />
        {evidence.sourceLabel ?? "Unlabeled source"}
      </span>
      <span className={cn(TYPE.meta, "shrink-0")}>
        {evidence.status === "missing"
          ? sourceStatusLabel(evidence.status)
          : `${count} evidence event${count === 1 ? "" : "s"}`}
      </span>
    </li>
  )
}

function ContributionBlock({ contribution }: { contribution: SignalContribution }) {
  const evidence = contribution.evidence ?? []
  return (
    <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[color:var(--g-text-primary)]">
          {contribution.label ?? "Signal"}
        </p>
        <span className={cn(TYPE.meta, "shrink-0")}>
          {contribution.points != null ? `+${contribution.points.toFixed(1)} pts` : "—"}
          {contribution.weight != null ? ` · weight ${contribution.weight.toFixed(2)}` : ""}
        </span>
      </div>
      {contribution.description ? (
        <p className={cn(TYPE.meta, "mt-0.5")}>{contribution.description}</p>
      ) : null}
      {evidence.length > 0 ? (
        <ul className="mt-1.5 border-t border-dashed border-divide pt-1.5">
          {evidence.map((row, idx) => (
            <EvidenceRow key={row.sourceId ?? idx} evidence={row} />
          ))}
        </ul>
      ) : (
        <p className={cn(TYPE.meta, "mt-1.5")}>No source evidence recorded for this signal.</p>
      )}
    </div>
  )
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

function WhyItem({ item, capturedAt }: { item: PriorityItem; capturedAt: string | undefined }) {
  const [open, setOpen] = useState(false)
  const contributions = item.signalContributions ?? []
  const explanations = item.explanations ?? []
  const gaps = item.gaps ?? []

  return (
    <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start justify-between gap-2 text-left"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
            {item.department ?? "org"}
          </p>
          <p className={TYPE.cardTitle}>{item.title ?? "Untitled priority"}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-right">
            <span className="block text-sm font-semibold tabular-nums">
              {item.priorityScore != null ? Math.round(item.priorityScore) : "—"}
              <span className="text-[10px] font-normal text-[color:var(--g-text-muted)]">/100</span>
            </span>
            <span className={cn("block text-[10px] font-medium uppercase", priorityBandTone(item.priorityBand))}>
              {item.priorityBand ?? "unscored"}
            </span>
          </span>
          <CaretDown
            className={cn("h-4 w-4 shrink-0 text-[color:var(--g-text-muted)] transition-transform", open && "rotate-180")}
            aria-hidden
          />
        </div>
      </button>

      {open ? (
        <div className="mt-3 space-y-3 border-t border-divide pt-3">
          <p className={TYPE.meta}>{relativeFreshness(capturedAt)}</p>

          {explanations.length > 0 ? (
            <ul className="space-y-1">
              {explanations.map((line, idx) => (
                <li key={idx} className={cn(TYPE.bodyMuted, "flex gap-1.5")}>
                  <span aria-hidden>•</span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={TYPE.meta}>No scored contributing signals for this item yet.</p>
          )}

          {contributions.length > 0 ? (
            <div className="space-y-2">
              <p className={TYPE.eyebrow}>Contributing signals &amp; sources</p>
              {contributions.map((contribution) => (
                <ContributionBlock key={contribution.signalId} contribution={contribution} />
              ))}
            </div>
          ) : null}

          {gaps.length > 0 ? (
            <div className="rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
              <p className={cn(TYPE.meta, "font-medium")}>Disclosed gaps</p>
              <ul className="mt-1 space-y-0.5">
                {gaps.map((gap, idx) => (
                  <li key={idx} className={TYPE.meta}>
                    {gap}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
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

  return (
    <section
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="why-gravitre-heading"
      data-why-gravitre-panel=""
    >
      <p className={TYPE.eyebrow}>Evidence</p>
      <h2 id="why-gravitre-heading" className={TYPE.sectionTitle}>
        Why Gravitre thinks this
      </h2>
      <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
        Real contributing signals, sources, and evidence counts behind the org&apos;s top-scored
        priorities — expand any item. Honest gaps are shown when a source isn&apos;t connected yet,
        never a fabricated evidence count.
      </p>

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
        <div className="mt-4 space-y-2">
          {top.map((item) => (
            <WhyItem key={item.workObjectId ?? item.title} item={item} capturedAt={data?.capturedAt} />
          ))}
        </div>
      )}
    </section>
  )
}
