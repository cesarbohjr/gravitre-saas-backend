"use client"

import { useId } from "react"
import { motion } from "framer-motion"
import type { PacketKind } from "./types"

const KIND_MID: Record<PacketKind, string> = {
  signal: "var(--info)",
  action: "var(--brand)",
  learn: "var(--g-intelligence)",
}

/**
 * Path TRACE — idle mineral stroke + sweeping gradient when active.
 * Learned edges stay as a permanent brand hairline (system remembered).
 */
export function GravitreSignalPath({
  d,
  activeKind = null,
  muted = false,
  reduced = false,
  learned = false,
}: {
  d: string
  activeKind?: PacketKind | null
  muted?: boolean
  reduced?: boolean
  learned?: boolean
}) {
  const uid = useId().replace(/:/g, "")
  const gradId = `gv-dept-path-${uid}`
  const active = activeKind != null

  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="var(--line)"
        strokeWidth={1.25}
        strokeLinecap="round"
        opacity={muted ? 0.2 : 0.65}
      />
      {learned && !active ? (
        <path
          d={d}
          fill="none"
          stroke="var(--brand)"
          strokeWidth={1.75}
          strokeLinecap="round"
          opacity={0.55}
        />
      ) : null}
      {active ? (
        <>
          <path
            d={d}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={2}
            strokeLinecap="round"
            opacity={muted ? 0.4 : 1}
          />
          <defs>
            {reduced ? (
              <linearGradient id={gradId} gradientUnits="userSpaceOnUse" x1="0%" x2="100%">
                <stop stopColor="var(--line)" />
                <stop offset="0.5" stopColor={KIND_MID[activeKind]} />
                <stop offset="1" stopColor="var(--line)" />
              </linearGradient>
            ) : (
              <motion.linearGradient
                id={gradId}
                gradientUnits="userSpaceOnUse"
                initial={{ x1: "-10%", x2: "0%", y1: 0, y2: 1 }}
                animate={{ x1: "110%", x2: "120%", y1: 0, y2: 1 }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  repeatType: "loop",
                  ease: "easeInOut",
                  repeatDelay: 0.4,
                }}
              >
                <stop stopColor="var(--line)" />
                <stop offset="0.5" stopColor={KIND_MID[activeKind]} />
                <stop offset="1" stopColor="var(--line)" />
              </motion.linearGradient>
            )}
          </defs>
        </>
      ) : null}
    </g>
  )
}
