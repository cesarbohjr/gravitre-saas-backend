"use client"

import type { CSSProperties } from "react"
import { motion } from "framer-motion"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import type { IntelligenceCoreDepartment } from "@/lib/api"
import { formatDepartmentLabel } from "./types"
import { cn } from "@/lib/utils"

const STATE_COPY: Record<IntelligenceCoreDepartment["state"], string> = {
  idle: "Idle",
  "flow-inward": "New activity",
  trace: "Active",
  "pending-approval": "Awaiting approval",
  resolved: "Resolved",
  "low-confidence": "Low confidence",
}

/**
 * Department card — same card language as GravitreDepartmentNode in the
 * marketing department network (rounded white card, brand accent on active,
 * pulse dot), positioned absolutely by the parent's radial layout, driven by
 * a real per-department state from GET /api/intelligence/core/state.
 */
export function DepartmentNode({
  department,
  reduced = false,
  style,
}: {
  department: IntelligenceCoreDepartment
  reduced?: boolean
  style?: CSSProperties
}) {
  const isActive = department.state === "flow-inward" || department.state === "trace"
  const isResolved = department.state === "resolved"
  const isPending = department.state === "pending-approval"
  const isLowConfidence = department.state === "low-confidence"

  return (
    <motion.div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={style}
      animate={!reduced ? { y: [0, -3, 0] } : { y: 0 }}
      transition={!reduced ? { duration: 3.6, repeat: Infinity, ease: "easeInOut" } : undefined}
    >
      <motion.div
        initial={false}
        animate={{ scale: isActive ? 1.03 : isResolved ? 1.01 : 1 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative z-20 flex max-w-[10.5rem] items-center gap-2 rounded-xl border bg-white px-3 py-2.5 text-left shadow-sm",
          isActive && "border-[color:var(--color-brand,#16a374)] shadow-md",
          isResolved && "border-[color:var(--color-brand,#16a374)]",
          isPending && "border-amber-500",
          !isActive && !isResolved && !isPending && "border-[color:var(--color-line,#eaedf1)]",
          isLowConfidence && "opacity-70",
        )}
      >
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[color:var(--g-surface-2,#f5f6f8)] text-[color:var(--g-text-secondary)]",
            isActive && "text-[color:var(--color-brand,#16a374)]",
            isResolved && "text-[color:var(--color-brand,#16a374)]",
            isPending && "text-amber-600",
          )}
        >
          <NucleoIntelligence className="h-4 w-4" />
        </span>
        <span className="min-w-0 pr-1">
          <span className="block truncate text-sm font-semibold text-[color:var(--g-text-secondary)]">
            {formatDepartmentLabel(department.id)}
          </span>
          <span className="block text-[10px] text-[color:var(--g-text-muted)]">
            {STATE_COPY[department.state]}
            {department.eventsInWindow > 0 ? ` · ${department.eventsInWindow} event${department.eventsInWindow === 1 ? "" : "s"}` : ""}
          </span>
        </span>
        <span
          className={cn(
            "absolute right-2 top-2 h-1.5 w-1.5 rounded-full",
            isActive
              ? "bg-[color:var(--color-brand,#16a374)]"
              : isResolved
                ? "bg-[color:var(--color-brand,#16a374)]"
                : isPending
                  ? "bg-amber-500"
                  : "bg-[color:var(--color-line,#eaedf1)]",
          )}
        />
        {isActive && !reduced ? (
          <motion.span
            aria-hidden
            className="pointer-events-none absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[color:var(--color-brand,#16a374)]"
            animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
          />
        ) : null}
        {isPending && !reduced ? (
          <motion.span
            aria-hidden
            className="pointer-events-none absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-amber-500"
            animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
          />
        ) : null}
      </motion.div>
    </motion.div>
  )
}
