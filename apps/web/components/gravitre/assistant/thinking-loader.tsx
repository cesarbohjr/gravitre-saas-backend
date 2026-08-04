"use client"

import { useId } from "react"

import { cn } from "@/lib/utils"

/**
 * GravitreThinkingLoader
 *
 * Animated Gravitre mark: a gooey/metaball SVG where two morphing bars and a
 * pulsing ellipse are fused by an SVG blur + color-matrix filter. Fill follows
 * `currentColor` so callers can set black-on-light (chat avatar) or theme ink.
 *
 * Filter ids are scoped with `useId` so multiple instances never collide.
 */
export function GravitreThinkingLoader({
  className,
  size = 28,
  title = "Gravitre AI is thinking",
}: {
  className?: string
  size?: number
  title?: string
}) {
  const rawId = useId()
  // Filter ids must be valid CSS/SVG identifiers (React's useId contains ":").
  const filterId = `gravitre-goo-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`

  // The gooey blur is authored in viewBox units tuned for a 72px render. Below
  // that, the 20-unit gap between the two bars is only a couple of device px,
  // so a fixed stdDeviation of 8 fuses them into an illegible smear. Scale the
  // blur down with the render size, clamped at 1 so 72px and larger stay
  // pixel-identical to what already ships in route transitions.
  const blur = (8 * Math.min(1, size / 72)).toFixed(2)

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={title}
      className={cn(
        "inline-flex shrink-0 items-center justify-center text-foreground",
        className,
      )}
      style={{ width: size, height: size, minWidth: size, minHeight: size }}
    >
      <svg
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        aria-hidden="true"
        focusable="false"
        style={{
          // Follow theme foreground: near-black on light, near-white on dark.
          ["--ink" as string]: "currentColor",
        }}
      >
        <defs>
          <filter id={filterId}>
            <feGaussianBlur in="SourceGraphic" stdDeviation={blur} result="b" />
            <feColorMatrix
              in="b"
              type="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 21 -10"
            />
          </filter>
        </defs>
        <g filter={`url(#${filterId})`} fill="var(--ink)">
          <path d="M 46.07345852918334 64.7731902523619 Q 52 58 61 58L 167 58 Q 176 58 170.3246663741498 64.98502600104639L 155.6753336258502 83.01497399895361 Q 150 90 141 90L 33 90 Q 24 90 29.926541470816662 83.2268097476381 Z" />
          <path d="M 46.07345852918334 116.7731902523619 Q 52 110 61 110L 167 110 Q 176 110 170.3246663741498 116.98502600104639L 155.6753336258502 135.01497399895362 Q 150 142 141 142L 33 142 Q 24 142 29.926541470816662 135.2268097476381 Z" />
          <ellipse cx="100" cy="100" rx="14" ry="8">
            <animate
              attributeName="ry"
              values="2;26;2"
              dur="2.4s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="rx"
              values="20;10;20"
              dur="2.4s"
              repeatCount="indefinite"
            />
          </ellipse>
        </g>
      </svg>
    </span>
  )
}
