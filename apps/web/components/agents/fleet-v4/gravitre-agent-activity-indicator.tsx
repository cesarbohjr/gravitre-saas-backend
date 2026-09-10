"use client"

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { isRuntimeWorking } from "./gravitre-agent-status"
import type { AgentRuntimeState } from "./types"

/** Restrained 3-segment activity indicator — not a glow orb. */
export function GravitreAgentActivityIndicator({
  runtimeState,
  className,
}: {
  runtimeState: AgentRuntimeState
  className?: string
}) {
  const reduce = useReducedMotion()
  const live = isRuntimeWorking(runtimeState)
  if (!live) return null

  return (
    <span
      className={cn("inline-flex h-3 items-end gap-0.5", className)}
      aria-hidden
      title="Agent working"
    >
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-0.5 rounded-full bg-[color:var(--g-brand)]/70"
          animate={
            reduce
              ? { height: 8 }
              : { height: [4, 10, 5, 8, 4], opacity: [0.45, 1, 0.6, 0.9, 0.45] }
          }
          transition={
            reduce
              ? undefined
              : { duration: 1.2, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }
          }
          style={{ height: 6 }}
        />
      ))}
    </span>
  )
}
