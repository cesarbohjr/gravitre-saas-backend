"use client"

import { motion } from "framer-motion"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { cn } from "@/lib/utils"
import { DEPARTMENT_META, type DepartmentId } from "./types"

/** Department id the app's department icons and tints know each card by. */
const APP_DEPARTMENT: Record<DepartmentId, string> = {
  sales: "sales",
  support: "customer_success",
  operations: "operations",
  finance: "finance",
}

/** What each department window shows while idle and once its story runs. */
const MESSAGE: Record<DepartmentId, { idle: string; active: string; resolved: string }> = {
  sales: { idle: "3 renewals due this week", active: "Sharing deal signals", resolved: "Context returned" },
  support: { idle: "Billing tickets rising", active: "Sharing ticket themes", resolved: "Context returned" },
  operations: { idle: "Vendor SLA review due", active: "Running the handoff", resolved: "Handoff verified" },
  finance: { idle: "Q3 forecast ready", active: "Checking the numbers", resolved: "Forecast reconciled" },
}

export type NodeVisualState = "idle" | "active" | "muted" | "resolved" | "focus"

/** Per-department stagger so the windows pop in one by one and never float in sync. */
const MOTION: Record<DepartmentId, { pop: number; delay: number; duration: number; distance: number }> = {
  sales: { pop: 0.1, delay: 0, duration: 3.6, distance: 4 },
  support: { pop: 0.25, delay: 0.45, duration: 4.1, distance: 3.5 },
  operations: { pop: 0.4, delay: 0.9, duration: 3.9, distance: 4.5 },
  finance: { pop: 0.55, delay: 1.35, duration: 3.4, distance: 3.5 },
}

/** Department window — a small toast-style app window in a grid cell. */
export function GravitreDepartmentNode({
  id,
  state = "idle",
  onHover,
  onLeave,
  onClick,
  interactive,
  reduced = false,
  align = "start",
}: {
  id: DepartmentId
  state?: NodeVisualState
  onHover?: () => void
  onLeave?: () => void
  onClick?: () => void
  interactive?: boolean
  reduced?: boolean
  align?: "start" | "end"
}) {
  const meta = DEPARTMENT_META[id]
  const isActive = state === "active" || state === "focus"
  const isResolved = state === "resolved"
  const isMuted = state === "muted"
  const m = MOTION[id]
  const message = isActive ? MESSAGE[id].active : isResolved ? MESSAGE[id].resolved : MESSAGE[id].idle

  return (
    <motion.div
      className={cn(align === "end" ? "ml-auto" : "mr-auto")}
      initial={reduced ? false : { opacity: 0, y: 14, scale: 0.94 }}
      whileInView={reduced ? undefined : { opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{ delay: m.pop, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      <motion.div
        animate={!reduced ? { y: [0, -m.distance, 0] } : { y: 0 }}
        transition={
          !reduced ? { duration: m.duration, delay: m.delay, repeat: Infinity, ease: "easeInOut" } : undefined
        }
      >
        <motion.button
          type="button"
          disabled={!interactive}
          aria-label={`${meta.label} department`}
          onMouseEnter={interactive ? onHover : undefined}
          onMouseLeave={interactive ? onLeave : undefined}
          onClick={interactive ? onClick : undefined}
          className={cn(
            "relative z-20 block w-[13.5rem] overflow-hidden rounded-xl border bg-card text-left shadow-[var(--shadow-aceternity)] transition-[border-color,opacity] duration-300",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
            isActive ? "border-brand" : isResolved ? "border-[color:var(--info)]" : "border-line",
            isMuted && "opacity-50",
            !interactive && "cursor-default",
          )}
          initial={false}
          animate={{ scale: isActive ? 1.03 : 1 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="flex items-center gap-1 border-b border-line px-3 py-1.5">
            <span className="size-1.5 rounded-full bg-line" />
            <span className="size-1.5 rounded-full bg-line" />
            <span className="size-1.5 rounded-full bg-line" />
            <span className="ml-1.5 font-mono text-[10px] text-[color:var(--g-text-muted)]">
              {meta.label.toLowerCase()}
            </span>
            <span className="relative ml-auto flex size-1.5">
              {isActive ? (
                <motion.span
                  aria-hidden
                  className="absolute inset-0 rounded-full bg-brand"
                  animate={{ scale: [1, 2.4], opacity: [0.7, 0] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
                />
              ) : null}
              <span
                className={cn(
                  "relative size-1.5 rounded-full",
                  isActive ? "bg-brand" : isResolved ? "bg-[color:var(--info)]" : "bg-brand/60",
                )}
              />
            </span>
          </span>
          <span className="flex items-center gap-3 px-3 py-3">
            <DepartmentIcon department={APP_DEPARTMENT[id]} size="md" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-[color:var(--g-text-primary)]">
                {meta.label}
              </span>
              <span className="block truncate text-xs text-[color:var(--g-text-muted)]">{message}</span>
            </span>
          </span>
        </motion.button>
      </motion.div>
    </motion.div>
  )
}
