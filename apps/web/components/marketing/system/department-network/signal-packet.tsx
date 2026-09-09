"use client"

import { useLayoutEffect, useRef, useState } from "react"
import type { PacketKind } from "./types"

const KIND_FILL: Record<PacketKind, string> = {
  signal: "var(--color-blue-500)",
  action: "var(--color-brand, #16a374)",
  learn: "color-mix(in oklch, var(--g-intelligence) 55%, #7c6af5)",
}

/**
 * Capsule packet positioned via SVG path getPointAtLength (TRANSFER semantics).
 */
export function GravitreSignalPacket({
  d,
  kind,
  progress,
}: {
  d: string
  kind: PacketKind
  progress: number
}) {
  const measureRef = useRef<SVGPathElement>(null)
  const [pose, setPose] = useState({ x: 0, y: 0, angle: 0 })

  useLayoutEffect(() => {
    const path = measureRef.current
    if (!path) return
    const len = path.getTotalLength()
    const at = Math.max(0, Math.min(1, progress)) * len
    const p = path.getPointAtLength(at)
    const p2 = path.getPointAtLength(Math.min(len, at + 2))
    const angle = (Math.atan2(p2.y - p.y, p2.x - p.x) * 180) / Math.PI
    setPose({ x: p.x, y: p.y, angle })
  }, [d, progress])

  return (
    <g>
      <path ref={measureRef} d={d} fill="none" stroke="none" aria-hidden />
      <g transform={`translate(${pose.x} ${pose.y}) rotate(${pose.angle})`}>
        <rect x={-8} y={-2.75} width={16} height={5.5} rx={2.75} fill={KIND_FILL[kind]} opacity={0.95} />
        <rect x={-6} y={-1.5} width={8} height={3} rx={1.5} fill="#fff" opacity={0.5} />
      </g>
    </g>
  )
}
