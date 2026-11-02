"use client"

/**
 * GravitreIntelligenceCore — the hub the department wiring runs into: the
 * Nodus white tile with the Gravitre mark, and a state chip underneath.
 */

import { AnimatePresence, motion } from "framer-motion"
import { NodusHub } from "@/components/marketing/nodus/scenes/kit"
import { CORE_STATE_LABEL, type CoreState } from "./types"

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
      >
        <NodusHub />
      </motion.div>

      <AnimatePresence mode="wait">
        {label ? (
          <motion.span
            key={state}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0 }}
            className="relative z-30 rounded-sm border border-brand bg-brand/10 px-2 py-0.5 text-xs text-brand"
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
