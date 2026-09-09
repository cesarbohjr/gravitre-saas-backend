"use client"

import { useId } from "react"
import { motion } from "framer-motion"
import type { PacketKind } from "./types"

const KIND_MID: Record<PacketKind, string> = {
  signal: "var(--color-blue-500)",
  action: "var(--color-brand, #16a374)",
  learn: "color-mix(in oklch, var(--g-intelligence) 55%, #7c6af5)",
}

/**
 * Path TRACE — idle mineral stroke + Nodus-style sweeping gradient when active
 * (same motion.linearGradient language as homepage HorizontalLine / RightSideSVG).
 */
export function GravitreSignalPath({
  d,
  activeKind = null,
  muted = false,
  reduced = false,
}: {
  d: string
  activeKind?: PacketKind | null
  muted?: boolean
  reduced?: boolean
}) {
  const uid = useId().replace(/:/g, "")
  const gradId = `gv-dept-path-${uid}`
  const active = activeKind != null

  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="var(--color-line, #eaedf1)"
        strokeWidth={1.25}
        strokeLinecap="round"
        opacity={muted ? 0.2 : 0.65}
      />
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
                <stop stopColor="var(--color-line, #EAEDF1)" />
                <stop offset="0.5" stopColor={KIND_MID[activeKind]} />
                <stop offset="1" stopColor="var(--color-line, #EAEDF1)" />
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
                <stop stopColor="var(--color-line, #EAEDF1)" />
                <stop offset="0.5" stopColor={KIND_MID[activeKind]} />
                <stop offset="1" stopColor="var(--color-line, #EAEDF1)" />
              </motion.linearGradient>
            )}
          </defs>
        </>
      ) : null}
    </g>
  )
}
