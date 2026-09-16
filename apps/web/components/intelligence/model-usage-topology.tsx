"use client"

import { useMemo } from "react"
import type { ModelCatalogDisplay } from "@/lib/intelligence/model-catalog-display"
import {
  buildModelUsageTopology,
  layoutModelUsageTopology,
  MODEL_USAGE_VB,
} from "@/lib/intelligence/model-usage-topology"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function ModelUsageTopology({ models, className }: { models: ModelCatalogDisplay[]; className?: string }) {
  const layout = useMemo(() => layoutModelUsageTopology(buildModelUsageTopology(models)), [models])

  if (models.length === 0) {
    return (
      <div
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-dashed border-divide px-4 py-8 text-center",
          className,
        )}
      >
        <p className={TYPE.cardTitle}>Usage topology</p>
        <p className={cn(TYPE.meta, "mt-1")}>
          Models appear here after they are registered. Callers are shown only when a model is
          deployed.
        </p>
      </div>
    )
  }

  return (
    <section
      className={cn("overflow-hidden rounded-[var(--np-radius-lg)] border border-divide", className)}
      aria-labelledby="model-usage-heading"
    >
      <div className="border-b border-divide px-4 py-3">
        <p id="model-usage-heading" className={TYPE.eyebrow}>
          Usage topology
        </p>
        <p className={cn(TYPE.meta, "mt-0.5")}>
          In-use models are deployed; others are registered but not in production.
        </p>
      </div>
      <div className="relative mx-auto aspect-[640/260] max-h-[260px] w-full">
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${MODEL_USAGE_VB.w} ${MODEL_USAGE_VB.h}`}
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
        {layout.nodes.map((node) => {
          const pos = layout.positions.get(node.id)
          if (!pos) return null
          return (
            <div
              key={node.id}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${(pos.x / MODEL_USAGE_VB.w) * 100}%`,
                top: `${(pos.y / MODEL_USAGE_VB.h) * 100}%`,
              }}
            >
              <div
                className={cn(
                  "max-w-[8rem] rounded-xl border px-2 py-1.5 text-center text-[11px] shadow-sm",
                  node.kind === "hub" &&
                    "max-w-[9rem] border-[color:var(--g-brand-border)] bg-[color:var(--g-intelligence-surface)] font-medium",
                  node.kind === "in_use" && "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]/40",
                  node.kind === "not_in_use" && "border-divide bg-[color:var(--g-surface-2)] text-muted-foreground",
                )}
              >
                {node.label}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
