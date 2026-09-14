"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { relativeFreshness, type PriorityItem } from "./why-gravitre-panel"
import {
  buildEvidenceGraph,
  EVIDENCE_GRAPH_VB,
  layoutEvidenceGraph,
  type EvidenceGraphNode,
} from "./evidence-graph-topology"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { CheckCircle, Circle, WarningCircle } from "@phosphor-icons/react"
import type { SourceStatus } from "./why-gravitre-panel"

function SourceStatusDot({ status }: { status?: SourceStatus }) {
  if (status === "live_connector") {
    return <CheckCircle className="h-3 w-3 text-[color:var(--g-success)]" weight="duotone" aria-hidden />
  }
  if (status === "missing") {
    return <WarningCircle className="h-3 w-3 text-amber-500" weight="duotone" aria-hidden />
  }
  return <Circle className="h-3 w-3 text-[color:var(--g-text-muted)]" weight="duotone" aria-hidden />
}

function GraphNode({
  node,
  x,
  y,
  selected,
}: {
  node: EvidenceGraphNode
  x: number
  y: number
  selected?: boolean
}) {
  const isInsight = node.kind === "insight"
  const isGap = node.kind === "gap"

  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{
        left: `${(x / EVIDENCE_GRAPH_VB.w) * 100}%`,
        top: `${(y / EVIDENCE_GRAPH_VB.h) * 100}%`,
      }}
    >
      <div
        className={cn(
          "max-w-[9rem] rounded-xl border bg-white px-2.5 py-2 text-center shadow-sm",
          isInsight && "max-w-[11rem] border-[color:var(--g-brand-border)] bg-[color:var(--g-intelligence-surface)] px-3 py-2.5",
          node.kind === "signal" && "border-[color:var(--color-brand,#16a374)]/40",
          node.kind === "source" && node.status === "missing" && "border-dashed border-amber-500/50 opacity-70",
          isGap && "max-w-none border-dashed border-divide bg-[color:var(--g-surface-2)]/80 px-3 py-1",
          selected && "ring-2 ring-[color:var(--g-brand)]",
          node.emphasis < 0.5 && !isGap && "opacity-60",
        )}
      >
        {isInsight && node.score != null ? (
          <p className="text-lg font-bold tabular-nums text-[color:var(--g-brand)]">
            {Math.round(node.score)}
            <span className="text-[10px] font-normal text-[color:var(--g-text-muted)]">/100</span>
          </p>
        ) : null}
        <p
          className={cn(
            "truncate text-xs font-semibold text-[color:var(--g-text-primary)]",
            isInsight && "text-sm",
            isGap && "whitespace-normal text-[10px] font-normal text-[color:var(--g-text-muted)]",
          )}
        >
          {node.label}
        </p>
        {node.sublabel && !isGap ? (
          <p className="mt-0.5 truncate text-[10px] capitalize text-[color:var(--g-text-muted)]">
            {node.kind === "source" ? (
              <span className="inline-flex items-center justify-center gap-1">
                <SourceStatusDot status={node.status} />
                {node.sublabel}
              </span>
            ) : (
              node.sublabel
            )}
          </p>
        ) : null}
      </div>
    </div>
  )
}

export function EvidenceGraphCanvas({
  item,
  className,
}: {
  item: PriorityItem
  className?: string
}) {
  const reduced = useReducedMotion()

  const layout = useMemo(() => layoutEvidenceGraph(buildEvidenceGraph(item)), [item])

  return (
    <div
      data-testid="evidence-graph-canvas"
      className={cn(
        "relative overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-gradient-to-b from-[color:var(--g-surface-2)]/30 to-[color:var(--g-surface-1)]",
        className,
      )}
      style={{ aspectRatio: `${EVIDENCE_GRAPH_VB.w} / ${EVIDENCE_GRAPH_VB.h}` }}
      role="img"
      aria-label={`Evidence graph for ${item.title ?? "priority"}`}
    >
      <svg
        viewBox={`0 0 ${EVIDENCE_GRAPH_VB.w} ${EVIDENCE_GRAPH_VB.h}`}
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      >
        {layout.edges.map((edge) => {
          const from = layout.positions.get(edge.fromId)
          const to = layout.positions.get(edge.toId)
          if (!from || !to) return null
          return (
            <line
              key={edge.id}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke={
                edge.dashed ? "var(--color-line,#cbd5e1)" : "var(--color-brand,#16a374)"
              }
              strokeWidth={edge.dashed ? 1 : 1.5}
              strokeDasharray={edge.dashed ? "4 4" : undefined}
              opacity={edge.dashed ? 0.45 : 0.65}
            />
          )
        })}
      </svg>

      {!reduced ? (
        <motion.div
          className="pointer-events-none absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35 }}
        />
      ) : null}

      {layout.nodes.map((node) => {
        const pos = layout.positions.get(node.id)
        if (!pos) return null
        return <GraphNode key={node.id} node={node} x={pos.x} y={pos.y} />
      })}
    </div>
  )
}

export function EvidenceGraphMeta({
  item,
  capturedAt,
  meta,
  className,
}: {
  item: PriorityItem
  capturedAt?: string
  meta: ReturnType<typeof buildEvidenceGraph>["meta"]
  className?: string
}) {
  const sourcesLine =
    meta.sourceLabels.length > 0 ? meta.sourceLabels.slice(0, 5).join(" · ") : "—"
  const explanations = item.explanations ?? []

  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-4", className)}>
      <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
        <p className={TYPE.eyebrow}>Evidence</p>
        <p className="text-sm font-semibold tabular-nums">
          {meta.totalEvidenceEvents > 0
            ? `${meta.totalEvidenceEvents} event${meta.totalEvidenceEvents === 1 ? "" : "s"}`
            : "—"}
        </p>
      </div>
      <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
        <p className={TYPE.eyebrow}>Sources</p>
        <p className="text-sm font-medium">{sourcesLine}</p>
      </div>
      <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
        <p className={TYPE.eyebrow}>Confidence</p>
        <p className="text-sm font-semibold capitalize">{item.priorityBand ?? "unscored"}</p>
      </div>
      <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
        <p className={TYPE.eyebrow}>Last updated</p>
        <p className="text-sm font-medium">{relativeFreshness(capturedAt)}</p>
      </div>
      {explanations.length > 0 ? (
        <div className="sm:col-span-2 lg:col-span-4 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] px-3 py-2">
          <p className={TYPE.eyebrow}>Contributing factors</p>
          <ul className="mt-1 space-y-0.5">
            {explanations.map((line, idx) => (
              <li key={idx} className={cn(TYPE.bodyMuted, "text-sm")}>
                {line}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {meta.gaps.length > 0 ? (
        <div className="sm:col-span-2 lg:col-span-4 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2">
          <p className={cn(TYPE.meta, "font-medium")}>Disclosed gaps</p>
          <ul className="mt-1 space-y-0.5">
            {meta.gaps.map((gap, idx) => (
              <li key={idx} className={TYPE.meta}>
                {gap}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
