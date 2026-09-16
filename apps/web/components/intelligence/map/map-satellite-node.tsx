"use client"

import { motion } from "framer-motion"
import type { MapNode } from "./map-topology"
import { cn } from "@/lib/utils"
import { BookOpen, Brain, Cpu, Lightning, Robot, Warning } from "@phosphor-icons/react"

export function MapSatelliteNode({
  node,
  reduced = false,
  selected = false,
  showLabel = true,
}: {
  node: MapNode
  reduced?: boolean
  selected?: boolean
  showLabel?: boolean
}) {
  const isActive = node.emphasis >= 0.85
  const Icon =
    node.kind === "agent"
      ? Robot
      : node.kind === "model"
        ? Cpu
        : node.kind === "learning"
          ? BookOpen
          : node.kind === "entity-type"
            ? Brain
            : node.kind === "signal"
              ? Warning
              : Lightning

  return (
    <motion.div
      animate={!reduced && isActive ? { y: [0, -2, 0] } : { y: 0 }}
      transition={!reduced ? { duration: 3.2, repeat: Infinity, ease: "easeInOut" } : undefined}
      className={cn(
        "flex max-w-[9.5rem] items-center gap-2 rounded-xl border bg-white px-2.5 py-2 text-left shadow-sm",
        isActive && "border-[color:var(--color-brand,#16a374)] shadow-md",
        node.kind === "signal" && "border-amber-500/60 bg-amber-50/80",
        node.emphasis < 0.5 && "opacity-50",
        selected && "ring-2 ring-[color:var(--g-brand)] ring-offset-1",
      )}
    >
      <span
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[color:var(--g-surface-2)]",
          isActive && "text-[color:var(--color-brand,#16a374)]",
          node.kind === "signal" && "text-amber-700",
        )}
      >
        <Icon className="h-3.5 w-3.5" weight="duotone" aria-hidden />
      </span>
      <span className="min-w-0">
        {showLabel ? (
          <span className="block truncate text-xs font-semibold text-[color:var(--g-text-secondary)]">
            {node.label}
          </span>
        ) : (
          <span className="sr-only">{node.label}</span>
        )}
        {showLabel && node.sublabel ? (
          <span className="block truncate text-[10px] capitalize text-[color:var(--g-text-muted)]">
            {node.sublabel}
          </span>
        ) : null}
      </span>
    </motion.div>
  )
}
