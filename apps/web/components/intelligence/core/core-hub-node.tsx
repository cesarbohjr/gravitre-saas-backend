"use client"

import { AnimatePresence, motion } from "framer-motion"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import type { IntelligenceCoreVisualState } from "@/lib/api"
import { CORE_STATE_LABEL } from "./types"
import { cn } from "@/lib/utils"

/**
 * Central hub — Nodus white tile (connectors/agents language) with the licensed
 * Nucleo Sharp brain-nodes glyph. Spin stays inside the tile; no overflowing rings.
 */
export function CoreHubNode({
  state,
  reduced = false,
}: {
  state: IntelligenceCoreVisualState
  reduced?: boolean
}) {
  const label = CORE_STATE_LABEL[state]
  const pulsing = state !== "idle" && state !== "resolved" && !reduced
  const resolved = state === "resolved"

  return (
    <div className="relative flex flex-col items-center gap-2">
      <motion.div
        initial={false}
        animate={{ scale: pulsing ? 1.03 : resolved ? 1.02 : 1 }}
        transition={{ duration: 0.35 }}
        className={cn(
          "relative h-20 w-20 overflow-hidden rounded-md bg-gray-200 p-px shadow-xl dark:bg-neutral-700 sm:h-24 sm:w-24",
          resolved && "ring-1 ring-[color:var(--color-brand,#16a374)]",
        )}
      >
        {!reduced ? (
          <>
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-blue-500)_20%,transparent_30%)]" />
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-delay:1s] [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-brand,#16a374)_20%,transparent_30%)]" />
          </>
        ) : null}
        <div className="relative z-20 flex h-full w-full flex-col items-center justify-center rounded-[5px] bg-white text-[color:var(--color-brand,#16a374)] dark:bg-neutral-900 dark:text-white">
          <NucleoIntelligence className="size-7 sm:size-8" />
          <span className="mt-0.5 text-[8px] font-bold text-[color:var(--g-text-muted)]">
            Core
          </span>
        </div>
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.span
          key={label}
          initial={reduced ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0 }}
          className="relative z-30 whitespace-nowrap rounded-sm border border-blue-500 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-500 shadow-sm dark:bg-blue-900 dark:text-white"
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}
