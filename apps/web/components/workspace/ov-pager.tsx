"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"

/** "1 of 8" previous/next control at the top of an inbox detail pane (v5). */
export function OvPager({
  position,
  count,
  onPrev,
  onNext,
}: {
  /** 1-based position of the open item in the visible list. */
  position: number
  count: number
  onPrev: () => void
  onNext: () => void
}) {
  if (count < 1 || position < 1) return null
  return (
    <span className="ov-pager" role="group" aria-label="Move between items">
      <button type="button" aria-label="Previous item" disabled={position <= 1} onClick={onPrev}>
        <ChevronLeft size={14} strokeWidth={2.2} aria-hidden />
      </button>
      <span aria-live="polite">
        {position} of {count}
      </span>
      <button type="button" aria-label="Next item" disabled={position >= count} onClick={onNext}>
        <ChevronRight size={14} strokeWidth={2.2} aria-hidden />
      </button>
    </span>
  )
}
