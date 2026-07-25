"use client"

import { useId } from "react"

import { cn } from "@/lib/utils"

/**
 * GravitreThinkingLoader
 *
 * A Claude-style "thinking" avatar: a gooey/metaball SVG where two morphing
 * bars and a pulsing ellipse are fused by an SVG blur + color-matrix filter,
 * producing an organic coral burst that breathes while the assistant works.
 *
 * The artwork is the exact SVG provided by the brand; the only changes are:
 *  - a `useId`-scoped filter id so multiple instances never collide, and
 *  - `fill` mapped to the brand coral token (`--chart-5`) so it renders
 *    correctly in both light and dark themes (falls back to a coral literal).
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

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={title}
      className={cn("inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        aria-hidden="true"
        focusable="false"
        style={{
          // Brand coral / terracotta (matches the ~#c8734f burst mark).
          ["--ink" as string]: "oklch(0.66 0.12 47)",
        }}
      >
        <defs>
          <filter id={filterId}>
            <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="b" />
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
