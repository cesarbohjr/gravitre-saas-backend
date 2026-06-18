"use client"

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { departmentTheme } from "@/lib/department-theme"

interface PackFrontArtProps {
  department: string | null | undefined
  packName: string
}

/**
 * The expressive front face of a flip pack card. This is the ONE deliberate
 * exception to the flat-icon rule — a larger, softly-lit presentation of the
 * SAME department icon used on the back face. It pulls icon + accent from
 * `departmentTheme` (the exact source the back card uses), so the flip reads
 * as one continuous object rotating, never two unrelated designs.
 */
export function PackFrontArt({ department, packName }: PackFrontArtProps) {
  const reduced = useReducedMotion()
  const theme = departmentTheme(department)
  const Icon = theme.icon

  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center gap-4 overflow-hidden p-8 text-center">
      {/* Soft radial glow in the pack's own hue — depth via color, not bevels. */}
      <div
        className={cn(
          "pointer-events-none absolute h-40 w-40 rounded-full opacity-60 blur-2xl",
          theme.soft,
        )}
        aria-hidden="true"
      />

      {/* Large icon chip with a slow, continuous float. */}
      <motion.div
        className={cn(
          "relative z-10 grid h-24 w-24 place-items-center rounded-2xl",
          theme.soft,
        )}
        animate={reduced ? undefined : { y: [0, -6, 0] }}
        transition={
          reduced
            ? undefined
            : { duration: 3, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
        }
      >
        <Icon className={cn("h-14 w-14", theme.ring)} aria-hidden />
      </motion.div>

      <div className="relative z-10 space-y-1">
        <p className="text-sm font-semibold text-foreground text-balance">{packName}</p>
        <p className="text-xs text-muted-foreground">Hover to preview · Tap to flip</p>
      </div>
    </div>
  )
}
