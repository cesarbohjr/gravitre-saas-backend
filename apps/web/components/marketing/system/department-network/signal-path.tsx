"use client"

import { motion } from "framer-motion"
import type { PacketKind } from "./types"

const KIND_STROKE: Record<PacketKind | "idle", string> = {
  idle: "color-mix(in oklch, var(--g-intelligence) 22%, #eaedf1)",
  signal: "var(--color-blue-500)",
  action: "var(--color-brand, #16a374)",
  learn: "color-mix(in oklch, var(--g-intelligence) 70%, #7c6af5)",
}

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
  const active = activeKind != null
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={KIND_STROKE.idle}
        strokeWidth={1.15}
        strokeLinecap="round"
        opacity={muted ? 0.18 : 0.5}
      />
      {active ? (
        <motion.path
          d={d}
          fill="none"
          stroke={KIND_STROKE[activeKind]}
          strokeWidth={1.75}
          strokeLinecap="round"
          initial={reduced ? false : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: muted ? 0.3 : 0.95 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        />
      ) : null}
    </g>
  )
}
