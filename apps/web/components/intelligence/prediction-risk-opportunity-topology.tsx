"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import type { BusinessPredictionDisplay } from "@/lib/intelligence/prediction-display"
import {
  buildPredictionTopology,
  layoutPredictionTopology,
  PREDICTION_TOPOLOGY_VB,
  type PredictionTopologyNode,
} from "@/lib/intelligence/prediction-topology"
import { partitionPredictionsByKind } from "@/lib/intelligence/prediction-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

function TopologyNode({
  node,
  x,
  y,
}: {
  node: PredictionTopologyNode
  x: number
  y: number
}) {
  const isHub = node.kind === "hub"
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{
        left: `${(x / PREDICTION_TOPOLOGY_VB.w) * 100}%`,
        top: `${(y / PREDICTION_TOPOLOGY_VB.h) * 100}%`,
      }}
    >
      <div
        className={cn(
          "max-w-[8.5rem] rounded-xl border px-2.5 py-2 text-center text-xs shadow-sm",
          isHub &&
            "max-w-[9.5rem] border-[color:var(--g-brand-border)] bg-[color:var(--g-intelligence-surface)] font-medium text-foreground",
          node.kind === "risk" && "border-[color:var(--g-approval-bright)]/35 bg-[color:var(--g-approval-soft)]/40",
          node.kind === "opportunity" && "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]/40",
          node.kind === "signal" && "border-divide bg-[color:var(--g-surface-2)]/80 text-muted-foreground",
        )}
      >
        <p className="leading-snug">{node.label}</p>
        {!isHub && node.confidence != null ? (
          <p className={cn(TYPE.meta, "mt-1 tabular-nums")}>{Math.round(node.confidence * 100)}%</p>
        ) : null}
      </div>
    </div>
  )
}

export function PredictionRiskOpportunityTopology({
  predictions,
  className,
}: {
  predictions: BusinessPredictionDisplay[]
  className?: string
}) {
  const reducedMotion = useReducedMotion()
  const layout = useMemo(() => {
    const { risks, opportunities, signals } = partitionPredictionsByKind(predictions)
    const graph = buildPredictionTopology(risks, opportunities, signals)
    return layoutPredictionTopology(graph)
  }, [predictions])

  if (layout.nodes.length <= 1) {
    return (
      <div
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-4 py-8 text-center",
          className,
        )}
      >
        <p className={TYPE.cardTitle}>Risk / opportunity topology</p>
        <p className={cn(TYPE.meta, "mt-1")}>
          Predictions will appear here once business signals include risks or opportunities.
        </p>
      </div>
    )
  }

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]",
        className,
      )}
      aria-labelledby="prediction-topology-heading"
    >
      <div className="border-b border-divide px-4 py-3">
        <p id="prediction-topology-heading" className={TYPE.eyebrow}>
          Risk / opportunity topology
        </p>
        <p className={cn(TYPE.meta, "mt-0.5")}>
          Risks on the left, opportunities on the right — connected through the prediction horizon.
        </p>
      </div>
      <div className="relative mx-auto aspect-[640/280] max-h-[280px] w-full">
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${PREDICTION_TOPOLOGY_VB.w} ${PREDICTION_TOPOLOGY_VB.h}`}
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
                stroke="currentColor"
                strokeOpacity={0.18}
                strokeWidth={1.5}
              />
            )
          })}
        </svg>
        <motion.div
          initial={reducedMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reducedMotion ? 0 : 0.25 }}
          className="absolute inset-0"
        >
          {layout.nodes.map((node) => {
            const pos = layout.positions.get(node.id)
            if (!pos) return null
            return <TopologyNode key={node.id} node={node} x={pos.x} y={pos.y} />
          })}
        </motion.div>
      </div>
    </section>
  )
}
