import { useId } from "react"

import { cn } from "@/lib/cn"

/**
 * The Gravitre mark, ported from
 * apps/web/components/gravitre/assistant/thinking-loader.tsx so the extension's
 * loading state is the app's loading state rather than a generic spinner
 * (Part B.4). Geometry, filter and timing are unchanged.
 *
 * The scale-aware blur is carried over deliberately: the two bars sit 20 units
 * apart in a 200-unit viewBox, so a fixed stdDeviation fuses them into a smear
 * below ~72px. Overlay loading states run at 44-56px, squarely in the range
 * that needed the fix.
 */
export function BrandLoader({
  size = 48,
  className,
  title = "Gravitre is working",
}: {
  size?: number
  className?: string
  title?: string
}) {
  const rawId = useId()
  const filterId = `gvt-goo-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`
  const blur = (8 * Math.min(1, size / 72)).toFixed(2)

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={title}
      className={cn("inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size, minWidth: size, minHeight: size }}
    >
      <svg
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        aria-hidden="true"
        focusable="false"
        style={{ ["--ink" as string]: "currentColor" }}
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

/**
 * Static version of the same mark for the header wordmark — no animation, so it
 * never draws the eye away from live content.
 */
export function BrandMark({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 200 200"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      className={cn("shrink-0", className)}
      fill="currentColor"
    >
      <path d="M 46.07345852918334 64.7731902523619 Q 52 58 61 58L 167 58 Q 176 58 170.3246663741498 64.98502600104639L 155.6753336258502 83.01497399895361 Q 150 90 141 90L 33 90 Q 24 90 29.926541470816662 83.2268097476381 Z" />
      <path d="M 46.07345852918334 116.7731902523619 Q 52 110 61 110L 167 110 Q 176 110 170.3246663741498 116.98502600104639L 155.6753336258502 135.01497399895362 Q 150 142 141 142L 33 142 Q 24 142 29.926541470816662 135.2268097476381 Z" />
    </svg>
  )
}
