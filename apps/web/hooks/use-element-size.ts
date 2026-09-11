"use client"

/**
 * Width *and* height of an element, for sizing that has to fit a container.
 *
 * `useElementWidth` already existed but reports width only, which is enough for
 * the float window's padding tiers and not enough for the voice orb: an orb sized
 * from width alone overflows a short container, because it shares that container
 * with a label, a subtitle and a control bar.
 *
 * Takes an element rather than a ref so it works with the `useState`-held nodes
 * the orb hosts use -- those exist only after an effect runs, and a ref would not
 * re-render the consumer when the node appears.
 */

import { useEffect, useState } from "react"

export type ElementSize = { width: number; height: number }

const ZERO: ElementSize = { width: 0, height: 0 }

export function useElementSize(element: HTMLElement | null): ElementSize {
  const [size, setSize] = useState<ElementSize>(ZERO)

  useEffect(() => {
    if (!element) {
      // Reset rather than keeping the last element's size: a stale size would
      // briefly paint the new container at the old container's dimensions.
      setSize(ZERO)
      return
    }

    const measure = (width: number, height: number) => {
      setSize((prev) => {
        const next = { width: Math.round(width), height: Math.round(height) }
        // ResizeObserver fires on sub-pixel changes; skipping equal values keeps
        // this out of the render path during a drag-resize.
        return prev.width === next.width && prev.height === next.height ? prev : next
      })
    }

    const rect = element.getBoundingClientRect()
    measure(rect.width, rect.height)

    // Absent in jsdom unless polyfilled, and in principle in older browsers. The
    // one-time measurement above still gives a usable size.
    if (typeof ResizeObserver === "undefined") return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      measure(entry.contentRect.width, entry.contentRect.height)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [element])

  return size
}
