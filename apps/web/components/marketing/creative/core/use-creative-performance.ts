"use client"

/**
 * Phase 11 — shared creative performance lifecycle for marketing scenes.
 * HIGH / MED / LOW / FALLBACK from reduced-motion, visibility, and save-data.
 */

import { useEffect, useState, type RefObject } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import {
  snapshotCreativePerformance,
  type CreativePerformanceSnapshot,
} from "./performance-manager"

function preferLowDevice(): boolean {
  if (typeof navigator === "undefined") return false
  const conn = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } })
    .connection
  if (conn?.saveData) return true
  if (conn?.effectiveType === "2g" || conn?.effectiveType === "slow-2g") return true
  return false
}

export function useCreativePerformance(
  rootRef: RefObject<HTMLElement | null>,
): CreativePerformanceSnapshot & { mounted: boolean } {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  const [hidden, setHidden] = useState(false)
  const [preferLow, setPreferLow] = useState(false)
  const inView = useInView(rootRef, { amount: 0.25, once: false })

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (!mounted) return
    setPreferLow(preferLowDevice())
  }, [mounted])

  const reduced = mounted && !!reducePreference
  const snap = snapshotCreativePerformance({
    reducedMotion: reduced,
    visible: inView,
    documentHidden: hidden,
    preferLow,
  })

  return { ...snap, mounted }
}
