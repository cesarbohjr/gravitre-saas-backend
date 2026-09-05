"use client"

/**
 * Aceternity-inspired vertical TRACE for marketing How-it-works only.
 * Progress follows the active step — not used on ops screens.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export function MarketingTracingBeam({
  activeIndex,
  total,
  className,
}: {
  activeIndex: number
  total: number
  className?: string
}) {
  const { reduced } = useMotionPrefs()
  const safeTotal = Math.max(total, 1)
  const progress = ((activeIndex + 1) / safeTotal) * 100

  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute bottom-4 left-5 top-4 w-px", className)}
    >
      <div className="absolute inset-0 rounded-full bg-border" />
      {reduced ? (
        <div
          className="absolute left-0 top-0 w-full rounded-full bg-primary/50"
          style={{ height: `${progress}%` }}
        />
      ) : (
        <motion.div
          className="absolute left-0 top-0 w-full origin-top rounded-full bg-gradient-to-b from-[color:var(--g-signal)] via-[color:var(--g-intelligence)] to-[color:var(--g-emerald)]"
          initial={false}
          animate={{ height: `${progress}%` }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        />
      )}
    </div>
  )
}
