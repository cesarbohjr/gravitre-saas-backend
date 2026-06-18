"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"

interface FlipPackCardProps {
  packId: string
  frontContent: React.ReactNode
  backContent: React.ReactNode
  className?: string
}

/**
 * A 3D flip card. The front face is the reveal/preview moment; the back face
 * holds the full (existing) card content. Flip is driven by hover on desktop
 * and tap on touch, and is keyboard-accessible (Enter/Space).
 *
 * Layout: an invisible in-flow clone of the back content reserves the card's
 * natural height, and the rotating layer is absolutely positioned over it — so
 * neither face causes layout shift and every card in a row stays the same
 * height. The flip uses pure CSS transforms (no JS animation lib needed) and
 * collapses to an instant swap under prefers-reduced-motion.
 */
export function FlipPackCard({
  packId,
  frontContent,
  backContent,
  className,
}: FlipPackCardProps) {
  const [isFlipped, setIsFlipped] = useState(false)

  const faceShell = cn(
    "absolute inset-0 h-full w-full overflow-hidden rounded-xl border border-border bg-card",
    "[backface-visibility:hidden]",
    "transition-[border-color,box-shadow] group-hover:border-primary/40 group-hover:shadow-md",
  )

  return (
    <div
      className={cn(
        "group relative w-full cursor-pointer [perspective:1200px]",
        "rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onMouseEnter={() => setIsFlipped(true)}
      onMouseLeave={() => setIsFlipped(false)}
      onClick={() => setIsFlipped((prev) => !prev)}
      role="button"
      tabIndex={0}
      aria-label={`${packId} pack card, ${
        isFlipped ? "showing details" : "showing preview"
      }, activate to flip`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          setIsFlipped((prev) => !prev)
        }
      }}
    >
      {/* Height spacer: in-flow, invisible (not focusable, removed from a11y
          tree) clone of the back content so the card reserves the correct,
          consistent height. */}
      <div className="invisible" aria-hidden="true">
        {backContent}
      </div>

      {/* Rotating layer, absolutely positioned over the spacer. */}
      <div
        className={cn(
          "absolute inset-0 transition-transform duration-500 [transform-style:preserve-3d]",
          "motion-reduce:transition-none",
          isFlipped && "[transform:rotateY(180deg)]",
        )}
        style={{ transitionTimingFunction: "cubic-bezier(0.4, 0, 0.2, 1)" }}
      >
        {/* FRONT FACE */}
        <div className={cn(faceShell, "flex items-center justify-center")}>
          {frontContent}
        </div>

        {/* BACK FACE — existing card content, untouched design */}
        <div className={cn(faceShell, "[transform:rotateY(180deg)]")}>
          {backContent}
        </div>
      </div>
    </div>
  )
}
