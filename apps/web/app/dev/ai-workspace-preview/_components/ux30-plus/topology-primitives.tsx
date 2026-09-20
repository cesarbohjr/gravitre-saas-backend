"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { useMotionPrefs } from "@/lib/animations"

const SPRING = { type: "spring" as const, stiffness: 280, damping: 28 }

export type TopologyNodeState = "idle" | "active" | "learned" | "warning" | "failed"

const NODE_STROKE: Record<TopologyNodeState, string> = {
  idle: "var(--g-border-default)",
  active: "var(--g-emerald)",
  learned: "var(--g-emerald)",
  warning: "var(--g-approval)",
  failed: "var(--g-danger)",
}

const NODE_FILL: Record<TopologyNodeState, string> = {
  idle: "var(--g-surface-1)",
  active: "color-mix(in oklch, var(--g-emerald) 8%, white)",
  learned: "color-mix(in oklch, var(--g-emerald) 5%, white)",
  warning: "color-mix(in oklch, var(--g-approval) 10%, white)",
  failed: "color-mix(in oklch, var(--g-danger) 8%, white)",
}

export function TopologyNode({
  x,
  y,
  label,
  sublabel,
  state = "idle",
  selected = false,
  kind = "entity",
  onClick,
  reducedMotion = false,
}: {
  x: number
  y: number
  label: string
  sublabel?: string
  state?: TopologyNodeState
  selected?: boolean
  kind?: string
  onClick?: () => void
  reducedMotion?: boolean
}) {
  const w = kind === "hub" ? 112 : 96
  const h = kind === "hub" ? 56 : 44
  const rx = kind === "hub" ? 12 : 8

  return (
    <g
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.()
      }}
      className="cursor-pointer outline-none focus-visible:[&_rect]:stroke-[var(--g-emerald)]"
    >
      <motion.rect
        x={x - w / 2}
        y={y - h / 2}
        width={w}
        height={h}
        rx={rx}
        fill={NODE_FILL[state]}
        stroke={selected ? "var(--g-emerald)" : NODE_STROKE[state]}
        strokeWidth={selected ? 2 : state === "idle" ? 1.25 : 1.75}
        animate={
          reducedMotion
            ? undefined
            : state === "active"
              ? { scale: [1, 1.02, 1] }
              : { scale: 1 }
        }
        transition={reducedMotion ? undefined : { duration: 1.2, repeat: state === "active" ? Infinity : 0, repeatDelay: 0.8 }}
      />
      <text
        x={x}
        y={y - (sublabel ? 4 : 0)}
        textAnchor="middle"
        className="fill-[color:var(--g-text-primary)] text-[11px] font-semibold"
      >
        {label}
      </text>
      {sublabel ? (
        <text
          x={x}
          y={y + 12}
          textAnchor="middle"
          className="fill-[color:var(--g-text-muted)] text-[9px]"
        >
          {sublabel}
        </text>
      ) : null}
    </g>
  )
}

export function TopologyEdge({
  x1,
  y1,
  x2,
  y2,
  label,
  state = "idle",
  active = false,
  learned = false,
  progress = 1,
  reducedMotion = false,
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  label?: string
  state?: "idle" | "active" | "learned"
  active?: boolean
  learned?: boolean
  progress?: number
  reducedMotion?: boolean
}) {
  const d = `M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`
  const stroke =
    state === "active" || active
      ? "var(--g-signal)"
      : learned || state === "learned"
        ? "var(--g-emerald)"
        : "var(--g-border-subtle)"
  const sw = learned ? 1.75 : active ? 2 : 1.25
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2

  return (
    <g>
      <path d={d} fill="none" stroke="var(--g-border-subtle)" strokeWidth={1.25} strokeLinecap="round" />
      <motion.path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={sw}
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={1}
        initial={false}
        animate={{ strokeDashoffset: reducedMotion ? 1 - progress : 1 - progress }}
        transition={reducedMotion ? { duration: 0 } : SPRING}
      />
      {label ? (
        <text x={midX} y={midY - 6} textAnchor="middle" className="fill-[color:var(--g-text-muted)] text-[8px]">
          {label}
        </text>
      ) : null}
    </g>
  )
}

export function HarnessSurface({
  children,
  className,
  elevated = true,
}: {
  children: React.ReactNode
  className?: string
  elevated?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[color:var(--g-border-subtle)]",
        elevated ? "bg-[color:var(--g-surface-1)] shadow-[var(--g-shadow-sm,0_1px_2px_rgba(0,0,0,0.04))]" : "bg-transparent",
        className,
      )}
    >
      {children}
    </div>
  )
}
