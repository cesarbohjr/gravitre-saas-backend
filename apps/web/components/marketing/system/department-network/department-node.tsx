"use client"

import type { ComponentType, SVGProps } from "react"
import { motion } from "framer-motion"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { PhoneIcon, RocketIcon, WalletIcon } from "@/components/marketing/nodus-icons/card-icons"
import { cn } from "@/lib/utils"
import { DEPARTMENT_META, type DepartmentId } from "./types"

const ICONS: Record<DepartmentId, ComponentType<SVGProps<SVGSVGElement>>> = {
  sales: RocketIcon,
  support: PhoneIcon,
  operations: NucleoWorkflow,
  finance: WalletIcon,
}

export type NodeVisualState = "idle" | "active" | "muted" | "resolved" | "focus"

export function GravitreDepartmentNode({
  id,
  x,
  y,
  state = "idle",
  onHover,
  onLeave,
  onClick,
  interactive,
}: {
  id: DepartmentId
  x: number
  y: number
  state?: NodeVisualState
  onHover?: () => void
  onLeave?: () => void
  onClick?: () => void
  interactive?: boolean
}) {
  const meta = DEPARTMENT_META[id]
  const Icon = ICONS[id]
  const isActive = state === "active" || state === "focus"
  const isResolved = state === "resolved"
  const isMuted = state === "muted"

  return (
    <motion.g
      transform={`translate(${x} ${y})`}
      initial={false}
      animate={{
        opacity: isMuted ? 0.35 : 1,
        scale: isActive ? 1.04 : isResolved ? 1.02 : 1,
      }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      style={{ cursor: interactive ? "pointer" : "default" }}
      onMouseEnter={interactive ? onHover : undefined}
      onMouseLeave={interactive ? onLeave : undefined}
      onClick={interactive ? onClick : undefined}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                onClick?.()
              }
            }
          : undefined
      }
      aria-label={`${meta.label} department`}
    >
      {/* Soft elevation disc */}
      <motion.circle
        r={36}
        fill="color-mix(in oklch, var(--g-intelligence) 8%, transparent)"
        initial={false}
        animate={{ opacity: isActive || isResolved ? 1 : 0 }}
        transition={{ duration: 0.4 }}
      />
      <rect
        x={-40}
        y={-28}
        width={80}
        height={56}
        rx={12}
        fill="#fff"
        stroke={
          isActive
            ? "color-mix(in oklch, var(--color-brand, #16a374) 55%, #eaedf1)"
            : isResolved
              ? "color-mix(in oklch, var(--color-blue-500) 45%, #eaedf1)"
              : "var(--color-line, #eaedf1)"
        }
        strokeWidth={1.25}
        className={cn(isActive && "drop-shadow-sm")}
      />
      {/* State indicator */}
      <circle
        cx={28}
        cy={-18}
        r={3.5}
        fill={
          isActive
            ? "var(--color-brand, #16a374)"
            : isResolved
              ? "var(--color-blue-500)"
              : "color-mix(in oklch, var(--g-text-muted) 35%, transparent)"
        }
      />
      {isActive ? (
        <motion.circle
          cx={28}
          cy={-18}
          r={3.5}
          fill="none"
          stroke="var(--color-brand, #16a374)"
          strokeWidth={1}
          initial={{ scale: 1, opacity: 0.7 }}
          animate={{ scale: 2.2, opacity: 0 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
        />
      ) : null}
      <foreignObject x={-12} y={-20} width={24} height={24}>
        <div className="flex h-6 w-6 items-center justify-center text-[color:var(--g-text-secondary)]">
          <Icon
            className={cn(
              "h-4 w-4",
              isActive && "text-[color:var(--color-brand,#16a374)]",
              isResolved && "text-[color:var(--color-blue-500)]",
            )}
          />
        </div>
      </foreignObject>
      <text
        y={22}
        textAnchor="middle"
        style={{ fontSize: 11, fontWeight: 600 }}
        className="fill-[color:var(--g-text-secondary)]"
      >
        {meta.label}
      </text>
    </motion.g>
  )
}
