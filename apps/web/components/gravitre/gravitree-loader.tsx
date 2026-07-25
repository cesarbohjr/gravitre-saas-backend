"use client"

import { useId } from "react"
import { cn } from "@/lib/utils"

export type GravitreeLoaderSize = "xs" | "sm" | "md" | "lg"

const sizeMap: Record<GravitreeLoaderSize, { width: number; height: number }> = {
  xs: { width: 28, height: 14 },
  sm: { width: 36, height: 18 },
  md: { width: 48, height: 24 },
  lg: { width: 64, height: 32 },
}

export interface GravitreeLoaderProps {
  size?: GravitreeLoaderSize
  className?: string
  label?: string
}

/** Gooey morphing loader — shared across page loads, chat thinking, and async states. */
export function GravitreeLoader({ size = "md", className, label = "Loading" }: GravitreeLoaderProps) {
  const filterId = useId().replace(/:/g, "")
  const { width, height } = sizeMap[size]

  return (
    <svg
      viewBox="0 0 80 40"
      width={width}
      height={height}
      className={cn("text-foreground", className)}
      role="status"
      aria-label={label}
    >
      <defs>
        <filter id={`goo-${filterId}`} x="-20%" y="-20%" width="140%" height="140%" colorInterpolationFilters="sRGB">
          <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
          <feColorMatrix
            in="blur"
            mode="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7"
            result="goo"
          />
          <feBlend in="SourceGraphic" in2="goo" />
        </filter>
      </defs>
      <g filter={`url(#goo-${filterId})`} fill="var(--ink, var(--foreground))">
        <rect x="8" y="12" width="14" height="16" rx="7">
          <animate attributeName="y" values="12;8;12" dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="height" values="16;24;16" dur="1.2s" repeatCount="indefinite" />
        </rect>
        <ellipse cx="40" cy="20" rx="10" ry="10">
          <animate attributeName="rx" values="10;14;10" dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="ry" values="10;6;10" dur="1.2s" repeatCount="indefinite" />
        </ellipse>
        <rect x="58" y="12" width="14" height="16" rx="7">
          <animate attributeName="y" values="12;16;12" dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="height" values="16;24;16" dur="1.2s" repeatCount="indefinite" />
        </rect>
      </g>
    </svg>
  )
}

/** Drop-in replacement for inline Lucide Loader2 spinners. */
export function LoadingIndicator({
  size = "sm",
  className,
  label,
}: {
  size?: GravitreeLoaderSize
  className?: string
  label?: string
}) {
  return <GravitreeLoader size={size} className={className} label={label ?? "Loading"} />
}
