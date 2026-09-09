"use client"

import { AnimatePresence, motion } from "framer-motion"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { CORE_STATE_LABEL, type CoreState } from "./types"
import { cn } from "@/lib/utils"

/**
 * Intelligence core — Nodus hub language (conic spin rings + mark), not a plain circle.
 */
export function GravitreIntelligenceCore({
  state = "idle",
  reduced = false,
}: {
  state?: CoreState
  reduced?: boolean
}) {
  const label = CORE_STATE_LABEL[state]
  const pulsing = state !== "idle" && state !== "verified" && state !== "learned" && !reduced
  const resolved = state === "verified" || state === "learned"

  return (
    <div className="absolute left-1/2 top-1/2 z-30 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2">
      {/* Concentric field rings */}
      <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
        {[88, 112, 136].map((size) => (
          <div
            key={size}
            className="absolute rounded-full border border-[color:color-mix(in_oklch,var(--g-intelligence)_18%,#eaedf1)]"
            style={{ width: size, height: size }}
          />
        ))}
        {!reduced ? (
          <motion.div
            className="absolute h-[100px] w-[100px] rounded-full border border-[color:color-mix(in_oklch,var(--color-brand,#16a374)_30%,transparent)]"
            animate={pulsing ? { scale: [1, 1.08, 1], opacity: [0.35, 0.7, 0.35] } : { scale: 1, opacity: 0.2 }}
            transition={{ duration: 2.4, repeat: pulsing ? Infinity : 0, ease: "easeInOut" }}
          />
        ) : null}
      </div>

      <motion.div
        initial={false}
        animate={{ scale: pulsing ? 1.03 : resolved ? 1.02 : 1 }}
        transition={{ duration: 0.35 }}
        className={cn(
          "relative h-16 w-16 overflow-hidden rounded-xl bg-gray-200 p-px shadow-xl dark:bg-neutral-700",
          resolved && "ring-1 ring-[color:var(--color-brand,#16a374)]",
        )}
      >
        {!reduced ? (
          <>
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-blue-500)_20%,transparent_30%)]" />
            <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-delay:1s] [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-brand,#16a374)_20%,transparent_30%)]" />
          </>
        ) : null}
        <div className="relative z-20 flex h-full w-full flex-col items-center justify-center rounded-[10px] bg-white text-[color:var(--color-brand,#16a374)]">
          <LogoSVG className="size-6" />
          <span className="mt-0.5 text-[8px] font-bold uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]">
            Core
          </span>
        </div>
      </motion.div>

      <AnimatePresence mode="wait">
        {label ? (
          <motion.span
            key={state}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0 }}
            className="relative z-30 rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2.5 py-1 text-[10px] font-semibold text-[color:var(--color-brand,#16a374)] shadow-sm"
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
