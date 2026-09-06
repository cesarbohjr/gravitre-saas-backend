"use client"

/**
 * ResolveMark — MOTION_CONCEPT.RESOLVE.
 * Successful completion check. One-shot scale-in unless reduced motion.
 */

import { motion } from "framer-motion"
import { Icon } from "@/lib/icons"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export type ResolveMarkProps = {
  className?: string
  size?: "sm" | "md" | "lg"
  label?: string
  /** When false, render static (already resolved). */
  animate?: boolean
}

const BOX = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
} as const

const ICON_SIZE = {
  sm: "xs" as const,
  md: "sm" as const,
  lg: "sm" as const,
}

export function ResolveMark({
  className,
  size = "md",
  label = "Verified",
  animate = true,
}: ResolveMarkProps) {
  const { reduced } = useMotionPrefs()
  const motionOn = animate && !reduced

  return (
    <motion.span
      role="img"
      aria-label={label}
      className={cn(
        "inline-flex items-center justify-center rounded-full bg-[color:var(--g-emerald)] text-[color:var(--primary-foreground)] shadow-[var(--g-shadow-subtle)]",
        BOX[size],
        className,
      )}
      initial={motionOn ? { scale: 0.6, opacity: 0 } : false}
      animate={{ scale: 1, opacity: 1 }}
      transition={
        motionOn
          ? { duration: 0.4, ease: [0.16, 1, 0.3, 1] }
          : { duration: 0 }
      }
    >
      <Icon name="check" size={ICON_SIZE[size]} className="text-inherit" aria-hidden />
    </motion.span>
  )
}
