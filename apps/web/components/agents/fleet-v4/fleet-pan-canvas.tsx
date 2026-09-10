"use client"

/**
 * Grab-to-pan + scrollable viewport for the TEAM topology canvas.
 * Interactive controls (cards, department drops) opt out via data-fleet-interactive.
 */

import { useRef, type PointerEvent, type ReactNode } from "react"
import { cn } from "@/lib/utils"

export function FleetPanCanvas({
  children,
  className,
  hint = "Drag empty space to pan · scroll for fine movement",
}: {
  children: ReactNode
  className?: string
  hint?: string
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const panRef = useRef<{
    active: boolean
    pointerId: number
    startX: number
    startY: number
    scrollLeft: number
    scrollTop: number
  } | null>(null)

  const endPan = (e: PointerEvent<HTMLDivElement>) => {
    const pan = panRef.current
    if (!pan || pan.pointerId !== e.pointerId) return
    panRef.current = null
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      /* already released */
    }
    e.currentTarget.classList.remove("cursor-grabbing")
    e.currentTarget.classList.add("cursor-grab")
  }

  return (
    <div className={cn("relative", className)}>
      <p className="mb-2 text-[10px] text-[color:var(--g-text-muted)]">{hint}</p>
      <div
        ref={viewportRef}
        role="region"
        aria-label="Fleet team canvas"
        className={cn(
          "max-h-[min(72vh,760px)] cursor-grab overflow-auto rounded-[var(--np-radius-lg)] border border-divide bg-white/40",
          "scrollbar-thin [scrollbar-color:var(--color-line,theme(colors.neutral.300))_transparent]",
        )}
        onPointerDown={(e) => {
          if (e.button !== 0 && e.button !== 1) return
          const el = e.target as HTMLElement | null
          if (el?.closest("[data-fleet-interactive]")) return
          const viewport = viewportRef.current
          if (!viewport) return
          panRef.current = {
            active: true,
            pointerId: e.pointerId,
            startX: e.clientX,
            startY: e.clientY,
            scrollLeft: viewport.scrollLeft,
            scrollTop: viewport.scrollTop,
          }
          viewport.setPointerCapture(e.pointerId)
          viewport.classList.remove("cursor-grab")
          viewport.classList.add("cursor-grabbing")
        }}
        onPointerMove={(e) => {
          const pan = panRef.current
          const viewport = viewportRef.current
          if (!pan?.active || pan.pointerId !== e.pointerId || !viewport) return
          viewport.scrollLeft = pan.scrollLeft - (e.clientX - pan.startX)
          viewport.scrollTop = pan.scrollTop - (e.clientY - pan.startY)
        }}
        onPointerUp={endPan}
        onPointerCancel={endPan}
      >
        <div className="min-h-[560px] min-w-[1180px] p-4 sm:p-5">{children}</div>
      </div>
    </div>
  )
}
