"use client"

import { useId } from "react"
import { motion } from "framer-motion"
import type { IntelligenceCoreVisualState } from "@/lib/api"

const STATE_MID: Partial<Record<IntelligenceCoreVisualState, string>> = {
  "flow-inward": "var(--g-electric)",
  trace: "var(--g-emerald)",
  "pending-approval": "var(--g-warmth)",
  resolved: "var(--g-emerald)",
}

/**
 * Edge between the core hub and a department node — same sweeping-gradient
 * technique as GravitreSignalPath in the marketing department network
 * (motion.linearGradient traveling along a static stroke), but the "active"
 * flag comes from a real department state, not a scripted beat.
 */
export function SignalEdge({
  x1,
  y1,
  x2,
  y2,
  state,
  reduced = false,
}: {
  x1: number
  y1: number
  x2: number
  y2: number
  state: IntelligenceCoreVisualState
  reduced?: boolean
}) {
  const uid = useId().replace(/:/g, "")
  const gradId = `gv-core-edge-${uid}`
  const mid = STATE_MID[state] ?? null
  const active = mid != null
  const routing = state === "flow-inward" || state === "trace"
  const lowConfidence = state === "low-confidence"

  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="var(--line)"
        strokeWidth={1.25}
        strokeDasharray={lowConfidence ? "4 4" : undefined}
        strokeLinecap="round"
        opacity={lowConfidence ? 0.35 : 0.55}
      />
      {active ? (
        <>
          <line
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={`url(#${gradId})`}
            strokeWidth={2}
            strokeLinecap="round"
          />
          <defs>
            {reduced || !routing ? (
              <linearGradient id={gradId} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x2} y2={y2}>
                <stop stopColor="var(--line)" />
                <stop offset="0.5" stopColor={mid} />
                <stop offset="1" stopColor="var(--line)" />
              </linearGradient>
            ) : (
              <motion.linearGradient
                id={gradId}
                gradientUnits="userSpaceOnUse"
                initial={{ x1, y1, x2: x1, y2: y1 }}
                animate={{ x1: x2, y1: y2, x2, y2 }}
                transition={{ duration: 1.6, repeat: Infinity, repeatType: "loop", ease: "easeInOut", repeatDelay: 0.4 }}
              >
                <stop stopColor="var(--line)" />
                <stop offset="0.5" stopColor={mid} />
                <stop offset="1" stopColor="var(--line)" />
              </motion.linearGradient>
            )}
          </defs>
        </>
      ) : null}
    </g>
  )
}
