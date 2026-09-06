"use client"

/**
 * PulseDot — MOTION_CONCEPT.PULSE.
 * Intelligence / signal active indicator. Respects reduced motion.
 */

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export type PulseDotTone = "intelligence" | "emerald" | "signal" | "approval"

const TONE: Record<PulseDotTone, string> = {
  intelligence: "var(--g-intelligence)",
  emerald: "var(--g-emerald)",
  signal: "var(--g-signal)",
  approval: "var(--g-approval)",
}

export type PulseDotProps = {
  tone?: PulseDotTone
  size?: "sm" | "md" | "lg"
  className?: string
  /** Accessible label when pulse conveys state alone. */
  label?: string
}

const SIZE = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
  lg: "h-2.5 w-2.5",
} as const

export function PulseDot({
  tone = "intelligence",
  size = "md",
  className,
  label = "Active",
}: PulseDotProps) {
  const { reduced } = useMotionPrefs()
  const color = TONE[tone]

  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center", SIZE[size], className)}
      role="status"
      aria-label={label}
    >
      {!reduced ? (
        <motion.span
          className="absolute inset-0 rounded-full opacity-40"
          style={{ backgroundColor: color }}
          animate={{ scale: [1, 2.2, 1], opacity: [0.45, 0, 0.45] }}
          transition={{
            duration: 1.6,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          aria-hidden
        />
      ) : null}
      <span
        className={cn("relative rounded-full", SIZE[size])}
        style={{ backgroundColor: color }}
        aria-hidden
      />
    </span>
  )
}
