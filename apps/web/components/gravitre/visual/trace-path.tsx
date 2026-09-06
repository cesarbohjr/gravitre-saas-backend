"use client"

/**
 * TracePath — MOTION_CONCEPT.TRACE.
 * Execution progress along an SVG path. Not decorative marquee.
 */

import { motion } from "framer-motion"
import { useId } from "react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export type TracePathTone = "intelligence" | "emerald" | "signal" | "approval"

const TONE: Record<TracePathTone, string> = {
  intelligence: "var(--g-intelligence)",
  emerald: "var(--g-emerald)",
  signal: "var(--g-signal)",
  approval: "var(--g-approval)",
}

export type TracePathProps = {
  /** SVG path `d` in viewBox coordinates. */
  d: string
  viewBox?: string
  tone?: TracePathTone
  className?: string
  /** 0–1 progress; when omitted and not reduced, gently loops once as demo. */
  progress?: number
  strokeWidth?: number
  /** Accessible description of what is progressing. */
  label?: string
}

export function TracePath({
  d,
  viewBox = "0 0 320 80",
  tone = "signal",
  className,
  progress,
  strokeWidth = 1.5,
  label = "Execution progress",
}: TracePathProps) {
  const { reduced } = useMotionPrefs()
  const id = useId()
  const color = TONE[tone]
  const controlled = typeof progress === "number"
  const offset = controlled ? 1 - Math.min(1, Math.max(0, progress)) : undefined

  return (
    <svg
      viewBox={viewBox}
      className={cn("h-auto w-full overflow-visible", className)}
      role="img"
      aria-label={label}
    >
      <path
        d={d}
        fill="none"
        stroke="var(--g-border-subtle)"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {reduced && controlled ? (
        <path
          d={d}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={offset}
        />
      ) : reduced ? (
        <path
          d={d}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          opacity={0.55}
        />
      ) : (
        <motion.path
          d={d}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          initial={controlled ? false : { strokeDashoffset: 1 }}
          animate={
            controlled
              ? { strokeDashoffset: offset }
              : { strokeDashoffset: [1, 0, 0] }
          }
          transition={
            controlled
              ? { duration: 0.45, ease: [0.4, 0, 0.2, 1] }
              : {
                  duration: 2.4,
                  times: [0, 0.7, 1],
                  repeat: Infinity,
                  repeatDelay: 1.2,
                  ease: [0.4, 0, 0.2, 1],
                }
          }
        />
      )}
      <defs>
        <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={color} stopOpacity={0.2} />
          <stop offset="100%" stopColor={color} stopOpacity={1} />
        </linearGradient>
      </defs>
    </svg>
  )
}

/** Default Hybrid B sequence path (intent → verified). */
export const TRACE_PATH_HYBRID_BEAT =
  "M 12 40 C 60 40, 80 40, 100 40 S 140 18, 180 40 S 220 62, 260 40 S 300 40, 308 40"
