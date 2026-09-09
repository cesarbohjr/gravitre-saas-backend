"use client"

import { memo } from "react"
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react"
import { cn } from "@/lib/utils"
import type { GraphNodeData } from "@/lib/relationships-graph/types"
import { TreeStructure } from "@phosphor-icons/react"

function RelationshipGraphNodeComponent({ data, selected }: NodeProps<Node<GraphNodeData>>) {
  return (
    <>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-divide !bg-background" />
      <div
        className={cn(
          "w-[196px] rounded-[var(--np-radius-md)] border bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[var(--np-shadow)] transition-shadow",
          data.isSeeded
            ? "border-[color:var(--g-brand)]/40 ring-1 ring-[color:var(--g-brand)]/10"
            : "border-divide",
          selected && "ring-2 ring-[color:var(--g-brand)]/50",
        )}
      >
        <div className="flex items-start gap-2">
          {data.isSeeded ? (
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
              <TreeStructure className="h-3.5 w-3.5" weight="duotone" aria-hidden />
            </span>
          ) : null}
          <div className="min-w-0 flex-1">
            <p className="truncate text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              {data.entityTypeLabel}
            </p>
            <p className="truncate text-sm font-medium text-[color:var(--g-text-primary)]">{data.label}</p>
            {data.isSeeded ? (
              <p className="mt-0.5 text-[10px] text-[color:var(--g-text-muted)]">Organization knowledge</p>
            ) : null}
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-divide !bg-background" />
    </>
  )
}

export const RelationshipGraphNode = memo(RelationshipGraphNodeComponent)

export const relationshipNodeTypes = {
  relationshipEntity: RelationshipGraphNode,
}
