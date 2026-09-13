"use client"

import Link from "next/link"
import type { IntelligenceMapSelection } from "./intelligence-map"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { formatDepartmentLabel } from "@/components/intelligence/core/types"
import { cn } from "@/lib/utils"
import { ArrowRight, Robot, Warning } from "@phosphor-icons/react"

export function IntelligenceMapContextPanel({
  selection,
  className,
}: {
  selection: IntelligenceMapSelection
  className?: string
}) {
  if (!selection) {
    return (
      <aside
        className={cn(
          "flex flex-col justify-center rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-1)]/80 p-5 backdrop-blur-sm",
          className,
        )}
      >
        <p className={TYPE.cardTitle}>Select a node on the map</p>
        <p className={cn(TYPE.bodyMuted, "mt-2")}>
          Switch lenses to explore knowledge, models, agents, predictions, and outcomes. Click any
          node to inspect live context here.
        </p>
      </aside>
    )
  }

  if (selection.kind === "signal") {
    const signal = selection.signal
    const title = readString(signal.title, "Business signal")
    const summary = readString(signal.summary, "")
    const score = Number(signal.quality_score ?? signal.confidence)
    const scoreLabel = Number.isFinite(score) ? `${Math.round(score)}% quality score` : null
    return (
      <aside
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-amber-500/40 bg-[color:var(--g-surface-1)]/95 p-5 shadow-[var(--np-shadow)] backdrop-blur-sm",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <Warning className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" weight="fill" aria-hidden />
          <div className="min-w-0">
            <p className={TYPE.eyebrow}>Needs attention</p>
            <h3 className={TYPE.sectionTitle}>{title}</h3>
            {summary ? <p className={cn(TYPE.bodyMuted, "mt-2")}>{summary}</p> : null}
            {scoreLabel ? <p className={cn(TYPE.meta, "mt-2")}>{scoreLabel}</p> : null}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href="/ai"
            className="inline-flex items-center gap-1 rounded-md bg-[color:var(--g-brand)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            Ask Gravitre why
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
          <Link
            href={APP_ROUTES.connectors}
            className="inline-flex items-center gap-1 rounded-md border border-divide px-3 py-1.5 text-xs font-medium hover:bg-[color:var(--g-surface-2)]"
          >
            See connectors
          </Link>
        </div>
      </aside>
    )
  }

  if (selection.kind === "agent") {
    const agent = selection.agent
    return (
      <aside
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]/95 p-5 shadow-[var(--np-shadow)] backdrop-blur-sm",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <Robot className="mt-0.5 h-5 w-5 shrink-0 text-[color:var(--g-intelligence)]" aria-hidden />
          <div>
            <p className={TYPE.eyebrow}>Agent</p>
            <h3 className={TYPE.sectionTitle}>{agent.name}</h3>
            <p className={cn(TYPE.bodyMuted, "mt-1")}>{agent.role}</p>
          </div>
        </div>
        <dl className={cn(TYPE.meta, "mt-4 space-y-2")}>
          <div className="flex justify-between gap-2">
            <dt>Status</dt>
            <dd className="font-medium capitalize">{agent.status}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Department</dt>
            <dd className="font-medium">{agent.department}</dd>
          </div>
          {agent.model ? (
            <div className="flex justify-between gap-2">
              <dt>Model</dt>
              <dd className="font-medium">{agent.model}</dd>
            </div>
          ) : null}
        </dl>
        <Link
          href={`${APP_ROUTES.agents}/${agent.id}`}
          className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open agent
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </aside>
    )
  }

  if (selection.kind === "department") {
    const department = selection.department
    return (
      <aside
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]/95 p-5 shadow-[var(--np-shadow)] backdrop-blur-sm",
          className,
        )}
      >
        <p className={TYPE.eyebrow}>Department</p>
        <h3 className={TYPE.sectionTitle}>{formatDepartmentLabel(department.id)}</h3>
        <dl className={cn(TYPE.meta, "mt-4 space-y-2")}>
          <div className="flex justify-between gap-2">
            <dt>State</dt>
            <dd className="font-medium capitalize">{department.state.replace(/-/g, " ")}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Events in window</dt>
            <dd className="font-medium tabular-nums">{department.eventsInWindow}</dd>
          </div>
          {department.confidence != null ? (
            <div className="flex justify-between gap-2">
              <dt>Confidence</dt>
              <dd className="font-medium tabular-nums">{Math.round(department.confidence * 100)}%</dd>
            </div>
          ) : null}
        </dl>
        <Link
          href={APP_ROUTES.intelligenceReports}
          className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open department reports
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </aside>
    )
  }

  const node = selection.node
  return (
    <aside
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]/95 p-5 shadow-[var(--np-shadow)] backdrop-blur-sm",
        className,
      )}
    >
      <p className={TYPE.eyebrow}>{node.kind.replace("-", " ")}</p>
      <h3 className={TYPE.sectionTitle}>{node.label}</h3>
      {node.sublabel ? <p className={cn(TYPE.bodyMuted, "mt-1 capitalize")}>{node.sublabel}</p> : null}
      {node.kind === "model" ? (
        <Link
          href={APP_ROUTES.training}
          className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open training
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      ) : null}
      {node.kind === "entity-type" ? (
        <Link
          href={APP_ROUTES.intelligenceMemory}
          className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open knowledge memory
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      ) : null}
    </aside>
  )
}
