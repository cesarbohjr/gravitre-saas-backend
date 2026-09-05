"use client"

/**
 * GravitreSignal — shared packet motif (Design Pass 2).
 * Extends MOTION_CONCEPT FLOW/TRACE/SIGNAL. Marketing Intelligence Field first.
 * Does not fork Orb/Wave.
 */

import { animate, motion, useMotionValue, useTransform } from "framer-motion"
import { useEffect, useId, useRef, useState } from "react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export type GravitreSignalTone =
  | "intelligence"
  | "operational"
  | "signal"
  | "pending"
  | "danger"

const TONE_CSS: Record<GravitreSignalTone, string> = {
  intelligence: "var(--g-intelligence)",
  operational: "var(--g-emerald)",
  signal: "var(--g-signal)",
  pending: "var(--g-warning)",
  danger: "var(--g-danger)",
}

export type GravitreSignalPhase =
  | "idle"
  | "travel"
  | "pause"
  | "resolve"
  | "fade"

type GravitreSignalProps = {
  path: string
  tone?: GravitreSignalTone
  reduced?: boolean
  className?: string
  cycleMs?: number
  delayMs?: number
}

/**
 * One concurrent packet: appear → travel → resolve flash → fade → calm pause.
 */
export function GravitreSignal({
  path,
  tone = "signal",
  reduced: reducedProp,
  className,
  cycleMs = 10000,
  delayMs = 800,
}: GravitreSignalProps) {
  const reactId = useId()
  const pathDomId = `gv-sig-${reactId.replace(/:/g, "")}`
  const pathRef = useRef<SVGPathElement>(null)
  const { reduced: prefsReduced } = useMotionPrefs()
  const reduced = reducedProp ?? prefsReduced
  const color = TONE_CSS[tone]

  const progress = useMotionValue(0)
  const opacity = useMotionValue(0)
  const [flash, setFlash] = useState(false)
  const [endPt, setEndPt] = useState({ x: 0, y: 0 })

  const cx = useTransform(progress, (t) => {
    const el = pathRef.current
    if (!el) return 0
    const len = el.getTotalLength()
    return el.getPointAtLength(Math.min(1, Math.max(0, t)) * len).x
  })
  const cy = useTransform(progress, (t) => {
    const el = pathRef.current
    if (!el) return 0
    const len = el.getTotalLength()
    return el.getPointAtLength(Math.min(1, Math.max(0, t)) * len).y
  })

  useEffect(() => {
    const el = pathRef.current
    if (!el) return
    const len = el.getTotalLength()
    const p = el.getPointAtLength(len)
    setEndPt({ x: p.x, y: p.y })
  }, [path])

  useEffect(() => {
    if (reduced) return
    let cancelled = false
    let pauseTimer: ReturnType<typeof setTimeout> | undefined
    const controls: { stop: () => void }[] = []

    const travelMs = Math.min(4000, Math.max(2400, cycleMs * 0.4))
    const pauseMs = Math.max(2800, cycleMs - travelMs - 900)

    const run = async () => {
      if (cancelled) return
      setFlash(false)
      progress.set(0)
      opacity.set(0)

      const fadeIn = animate(opacity, 1, { duration: 0.35, ease: [0.22, 1, 0.36, 1] })
      controls.push(fadeIn)
      await fadeIn.finished
      if (cancelled) return

      const travel = animate(progress, 1, {
        duration: travelMs / 1000,
        ease: [0.45, 0, 0.55, 1],
      })
      controls.push(travel)
      await travel.finished
      if (cancelled) return

      setFlash(true)
      const fadeOut = animate(opacity, 0, {
        duration: 0.45,
        ease: [0.16, 1, 0.3, 1],
        delay: 0.2,
      })
      controls.push(fadeOut)
      await fadeOut.finished
      if (cancelled) return
      setFlash(false)
      progress.set(0)

      pauseTimer = setTimeout(run, pauseMs)
    }

    const start = setTimeout(run, delayMs)
    return () => {
      cancelled = true
      clearTimeout(start)
      if (pauseTimer) clearTimeout(pauseTimer)
      controls.forEach((c) => c.stop())
    }
  }, [reduced, cycleMs, delayMs, path, progress, opacity])

  if (reduced) {
    return (
      <g aria-hidden className={className}>
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeOpacity={0.16}
          strokeWidth={1}
        />
        <circle cx={endPt.x || 560} cy={endPt.y || 200} r={3} fill={color} fillOpacity={0.4} />
      </g>
    )
  }

  return (
    <g aria-hidden className={cn(className)}>
      <path
        ref={pathRef}
        id={pathDomId}
        d={path}
        fill="none"
        stroke={color}
        strokeOpacity={0.14}
        strokeWidth={1}
      />
      <motion.circle r={3.5} fill={color} style={{ cx, cy, opacity }} />
      {flash ? (
        <motion.circle
          cx={endPt.x}
          cy={endPt.y}
          r={10}
          fill={
            tone === "operational" || tone === "intelligence" ? color : "var(--g-emerald)"
          }
          initial={{ opacity: 0.4, scale: 0.5 }}
          animate={{ opacity: 0, scale: 1.8 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        />
      ) : null}
    </g>
  )
}
