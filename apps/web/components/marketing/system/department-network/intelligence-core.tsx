"use client"

/**
 * GravitreIntelligenceCore — the hub the department wiring runs into: the
 * Nodus white tile with the Gravitre mark, and a state chip underneath.
 */

import { AnimatePresence, motion } from "framer-motion"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { CORE_STATE_LABEL, type CoreState } from "./types"
import { cn } from "@/lib/utils"

export function GravitreIntelligenceCore({
  state = "idle",
  reduced = false,
}: {
  state?: CoreState
  reduced?: boolean
  /** Kept for callers; the hub no longer draws session density. */
  learnedEdgeCount?: number
}) {
  const label = CORE_STATE_LABEL[state]
  const resolved = state === "verified" || state === "learned"
  const busy = state !== "idle" && !resolved

  return (
    <div className="relative flex flex-col items-center gap-2">
      <motion.div
        initial={false}
        animate={{ scale: busy ? 1.04 : 1 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative flex size-[5.5rem] items-center justify-center rounded-2xl border bg-card shadow-[var(--shadow-aceternity)]",
          resolved ? "border-brand" : "border-line",
        )}
      >
        <LogoSVG className="size-9 text-foreground" />
      </motion.div>

      <AnimatePresence mode="wait">
        {label ? (
          <motion.span
            key={state}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0 }}
            className="relative z-30 rounded-md border border-line bg-card px-2.5 py-1 text-[10px] font-semibold text-brand shadow-sm"
          >
            {label}
          </motion.span>
        ) : (
          <span className="h-[26px]" aria-hidden />
        )}
      </AnimatePresence>
    </div>
  )
}
