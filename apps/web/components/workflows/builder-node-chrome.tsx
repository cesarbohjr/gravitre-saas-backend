"use client"

import type { ComponentType, SVGProps } from "react"
import { cn } from "@/lib/utils"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { ROLE_ICON_REGISTRY, suggestRoleIcon } from "@/components/agents/fleet-v4/identity-tokens"
import { DEPARTMENT_ICONS, ROLE_DEPARTMENT, departmentIdFor } from "@/lib/department-icons"
import type { AgentRoleIconId } from "@/components/agents/fleet-v4/types"

/**
 * Shared visual chrome for workflow builder nodes: handles, header mark,
 * selection surface and default footprints. Visual only — connection
 * semantics stay in the builder's drag/drop handlers.
 */

/** Connection-drag relationship between a node and the node being dragged from. */
export type NodeConnectState = "idle" | "source" | "valid" | "invalid"

export type NodeHandleSide = "left" | "right" | "top" | "bottom"

const HANDLE_POSITION: Record<NodeHandleSide, string> = {
  left: "left-0 top-1/2 -translate-x-1/2 -translate-y-1/2",
  right: "right-0 top-1/2 translate-x-1/2 -translate-y-1/2",
  top: "top-0 left-1/2 -translate-x-1/2 -translate-y-1/2",
  bottom: "bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2",
}

type DragStart = (nodeId: string, e: React.MouseEvent | React.TouchEvent) => void

interface NodeHandleProps {
  side: NodeHandleSide
  nodeId: string
  nodeName: string
  selected: boolean
  connectState: NodeConnectState
  isDraggingConnection?: boolean
  onConnectionDragStart?: DragStart
  onConnectionDrop?: (nodeId: string) => void
}

/** 8px dot inside a 20px (24px touch) hit area. Side handles are faint at rest; top/bottom reveal on hover, focus or selection. */
export function NodeHandle({
  side,
  nodeId,
  nodeName,
  selected,
  connectState,
  isDraggingConnection,
  onConnectionDragStart,
  onConnectionDrop,
}: NodeHandleProps) {
  const primary = side === "left" || side === "right"
  const revealed = selected || connectState !== "idle"

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Connect from ${nodeName}`}
      data-handle={side}
      data-connect-state={connectState}
      onMouseDown={(e) => onConnectionDragStart?.(nodeId, e)}
      onTouchStart={(e) => {
        e.stopPropagation()
        if (e.touches.length === 1) onConnectionDragStart?.(nodeId, e)
      }}
      onMouseUp={() => isDraggingConnection && onConnectionDrop?.(nodeId)}
      onTouchEnd={() => isDraggingConnection && onConnectionDrop?.(nodeId)}
      onKeyDown={(e) => e.key === "Enter" && onConnectionDragStart?.(nodeId, e as unknown as React.MouseEvent)}
      title={connectState === "invalid" ? "Already connected" : "Drag to connect"}
      className={cn(
        "group/handle absolute z-10 flex h-6 w-6 items-center justify-center rounded-full outline-none md:h-5 md:w-5",
        HANDLE_POSITION[side],
        connectState === "invalid" ? "cursor-not-allowed" : "cursor-crosshair",
        primary || revealed ? "opacity-100" : "opacity-0 focus-visible:opacity-100 group-hover/node:opacity-100",
      )}
    >
      <span aria-hidden className={handleDotClass(connectState, selected)} />
    </div>
  )
}

/** The visible 8px handle dot; the parent must carry `group/handle`. */
export function handleDotClass(connectState: NodeConnectState, selected: boolean): string {
  return cn(
    "block h-2 w-2 rounded-full border transition-[transform,background-color,border-color,opacity] duration-150",
    "group-focus-visible/handle:ring-2 group-focus-visible/handle:ring-ring group-focus-visible/handle:ring-offset-1 group-focus-visible/handle:ring-offset-background",
    connectState === "source"
      ? "border-[var(--g-emerald)] bg-[var(--g-emerald)]"
      : connectState === "valid"
        ? "scale-125 border-[var(--g-emerald)] bg-card group-hover/handle:bg-[var(--g-emerald)]"
        : connectState === "invalid"
          ? "border-[color:var(--g-border-default)] bg-muted opacity-50"
          : selected
            ? "border-[var(--g-emerald)] bg-card group-hover/handle:scale-125 group-hover/handle:bg-[var(--g-emerald)]"
            : "border-[color:var(--g-border-strong)] bg-card group-hover/handle:scale-125 group-hover/handle:border-foreground",
  )
}

/** All four handles with shared props. */
export function NodeHandles(props: Omit<NodeHandleProps, "side">) {
  return (
    <>
      <NodeHandle side="left" {...props} />
      <NodeHandle side="right" {...props} />
      <NodeHandle side="top" {...props} />
      <NodeHandle side="bottom" {...props} />
    </>
  )
}

/** Node surface: quiet at rest; Emerald means selected/connected intelligence. */
export function nodeSurfaceClass(selected: boolean): string {
  return selected
    ? "border-[var(--g-emerald)] bg-[color:var(--g-emerald-pale)] shadow-[0_14px_34px_-30px_color-mix(in_srgb,var(--g-brand-active)_60%,transparent)] dark:bg-[var(--graphite-800)]"
    : "border-[color:var(--g-border-default)] bg-card transition-[border-color,box-shadow] duration-200 hover:border-[color:var(--g-emerald)] hover:shadow-[0_14px_34px_-32px_color-mix(in_srgb,var(--g-carbon)_50%,transparent)]"
}

/** 2px Signal edge on the leading side of a selected node. */
export function NodeSelectionEdge() {
  return (
    <span
      aria-hidden
      className="pointer-events-none absolute -left-px bottom-2 top-2 w-[2px] rounded-full bg-[var(--g-emerald)]"
    />
  )
}

type GlyphComponent = ComponentType<SVGProps<SVGSVGElement> & { strokeWidth?: number | string }>

/** Header mark: vendor logo when the step is bound to a provider, else the internal Lucide glyph in its category colour. */
export function NodeMark({ vendor, icon: Icon, tint }: { vendor?: string | null; icon: GlyphComponent; tint?: string }) {
  return (
    <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center">
      {vendor ? (
        <ProviderLogo provider={vendor} size="md" />
      ) : (
        <Icon
          className="h-[18px] w-[18px] text-[color:var(--g-text-secondary)]"
          style={tint ? { color: tint } : undefined}
          strokeWidth={1.75}
          aria-hidden
        />
      )}
    </span>
  )
}

/** Category colour bar along the top edge of a step card. */
export function NodeCategoryBar({ color }: { color: string }) {
  return (
    <span
      aria-hidden
      data-node-category-bar
      className="pointer-events-none absolute inset-x-3 top-0 h-[3px] rounded-b-full"
      style={{ background: color }}
    />
  )
}

/**
 * Mark for an agent step: the department's icon. Uses the step's configured
 * department, else the department its role or name points to.
 */
export function agentStepRole(config: Record<string, unknown> | undefined, name: string): {
  id: AgentRoleIconId
  label: string
  Icon: GlyphComponent
} {
  const roleText = typeof config?.role === "string" ? config.role : ""
  const department = typeof config?.department === "string" ? config.department : ""
  const id = suggestRoleIcon(roleText, name, department)
  const entry = ROLE_ICON_REGISTRY[id]
  const dept = department ? departmentIdFor(department) : ROLE_DEPARTMENT[id]
  return { id, label: roleText || entry.label, Icon: DEPARTMENT_ICONS[dept] as GlyphComponent }
}

/** Default rendered footprint per node family; measured sizes override these when available. */
export function nodeFootprint(type: string): { w: number; h: number } {
  if (type === "decision") return { w: DECISION_GEOMETRY.columnWidth, h: DECISION_GEOMETRY.square }
  if (type === "council") return { w: 256, h: 104 }
  return { w: 224, h: 80 }
}

/** Decision diamond: a square rotated 45° and centred in a fixed-width column; handles sit on its tips. */
export const DECISION_GEOMETRY = { columnWidth: 192, square: 128 } as const

export type NodeAnchorSide = "left" | "right" | "top" | "bottom"

export function nodeCenter(
  type: string,
  position: { x: number; y: number },
  size: { w: number; h: number },
): { x: number; y: number } {
  if (type === "decision") {
    return { x: position.x + DECISION_GEOMETRY.columnWidth / 2, y: position.y + DECISION_GEOMETRY.square / 2 }
  }
  return { x: position.x + size.w / 2, y: position.y + size.h / 2 }
}

/** Handle centre on the given side — the point an edge must meet. */
export function nodeAnchor(
  type: string,
  position: { x: number; y: number },
  size: { w: number; h: number },
  side: NodeAnchorSide,
): { x: number; y: number } {
  const c = nodeCenter(type, position, size)
  const rx = type === "decision" ? (DECISION_GEOMETRY.square / 2) * Math.SQRT2 : size.w / 2
  const ry = type === "decision" ? (DECISION_GEOMETRY.square / 2) * Math.SQRT2 : size.h / 2
  if (side === "left") return { x: c.x - rx, y: c.y }
  if (side === "right") return { x: c.x + rx, y: c.y }
  if (side === "top") return { x: c.x, y: c.y - ry }
  return { x: c.x, y: c.y + ry }
}
