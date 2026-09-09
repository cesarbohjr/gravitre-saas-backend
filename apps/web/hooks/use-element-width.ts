"use client"

import { useEffect, useState, type RefObject } from "react"
import { floatContentTiers, type FloatContentTier } from "@/lib/float-content-tiers"

export type { FloatContentTier }
export { floatContentTiers }

/** ResizeObserver-backed width of an element — for Float content tiers (spec §13). */
export function useElementWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      setWidth(Math.round(entry.contentRect.width))
    })
    ro.observe(el)
    setWidth(Math.round(el.getBoundingClientRect().width))
    return () => ro.disconnect()
  }, [ref])

  return width
}
