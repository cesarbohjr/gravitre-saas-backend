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

/** HTML department card — positioned with CSS so Motion never fights SVG transforms. */
export function GravitreDepartmentNode({
  id,
  state = "idle",
  onHover,
  onLeave,
  onClick,
  interactive,
}: {
  id: DepartmentId
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
    <motion.button
      type="button"
      disabled={!interactive}
      aria-label={`${meta.label} department`}
      onMouseEnter={interactive ? onHover : undefined}
      onMouseLeave={interactive ? onLeave : undefined}
      onClick={interactive ? onClick : undefined}
      className={cn(
        "absolute z-20 flex -translate-x-1/2 -translate-y-1/2 items-center gap-2.5 rounded-xl border bg-white px-3 py-2.5 text-left shadow-sm transition-shadow",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-brand,#16a374)]/40",
        isActive && "border-[color:var(--color-brand,#16a374)] shadow-md",
        isResolved && "border-[color:var(--color-blue-500)]",
        !isActive && !isResolved && "border-[color:var(--color-line,#eaedf1)]",
        isMuted && "opacity-40",
        !interactive && "cursor-default",
      )}
      style={{ left: meta.left, top: meta.top }}
      initial={false}
      animate={{ scale: isActive ? 1.04 : isResolved ? 1.02 : 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[color:var(--g-surface-2,#f5f6f8)] text-[color:var(--g-text-secondary)]",
          isActive && "text-[color:var(--color-brand,#16a374)]",
          isResolved && "text-[color:var(--color-blue-500)]",
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="pr-1">
        <span className="block text-sm font-semibold text-[color:var(--g-text-secondary)]">{meta.label}</span>
        <span className="block text-[10px] text-[color:var(--g-text-muted)]">
          {isActive ? "Active" : isResolved ? "Resolved" : "Ready"}
        </span>
      </span>
      <span
        className={cn(
          "absolute right-2 top-2 h-1.5 w-1.5 rounded-full",
          isActive
            ? "bg-[color:var(--color-brand,#16a374)]"
            : isResolved
              ? "bg-[color:var(--color-blue-500)]"
              : "bg-[color:var(--color-line,#eaedf1)]",
        )}
      />
      {isActive ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[color:var(--color-brand,#16a374)]"
          animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
        />
      ) : null}
    </motion.button>
  )
}
