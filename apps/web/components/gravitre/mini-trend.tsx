import { cn } from "@/lib/utils"

/**
 * Lightweight inline SVG micro-visuals that inherit the surrounding text color
 * via `currentColor`, so each surface tints them with its own accent token.
 * No chart dependency — these are decorative-but-honest at-a-glance trends.
 */

type SparklineProps = {
  values: number[]
  className?: string
  width?: number
  height?: number
  strokeWidth?: number
  /** Render a soft area fill under the line. */
  fill?: boolean
  "aria-label"?: string
}

export function Sparkline({
  values,
  className,
  width = 64,
  height = 20,
  strokeWidth = 1.5,
  fill = false,
  "aria-label": ariaLabel,
}: SparklineProps) {
  if (!values || values.length < 2) {
    return <span className={cn("inline-block h-[20px] w-16", className)} aria-hidden />
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const stepX = width / (values.length - 1)
  const pad = strokeWidth

  const points = values.map((v, i) => {
    const x = i * stepX
    const y = pad + (height - pad * 2) * (1 - (v - min) / range)
    return [x, y] as const
  })

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ")
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      className={cn("overflow-visible", className)}
      role="img"
      aria-label={ariaLabel ?? "trend"}
    >
      {fill && <path d={areaPath} fill="currentColor" opacity={0.12} />}
      <path
        d={linePath}
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

type MiniBarsProps = {
  values: number[]
  className?: string
  width?: number
  height?: number
  gap?: number
  "aria-label"?: string
}

export function MiniBars({
  values,
  className,
  width = 64,
  height = 20,
  gap = 2,
  "aria-label": ariaLabel,
}: MiniBarsProps) {
  if (!values || values.length === 0) {
    return <span className={cn("inline-block h-[20px] w-16", className)} aria-hidden />
  }

  const max = Math.max(...values) || 1
  const barW = (width - gap * (values.length - 1)) / values.length

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
      role="img"
      aria-label={ariaLabel ?? "distribution"}
    >
      {values.map((v, i) => {
        const h = Math.max(1, (v / max) * height)
        const x = i * (barW + gap)
        const y = height - h
        return <rect key={i} x={x} y={y} width={barW} height={h} rx={1} fill="currentColor" opacity={0.85} />
      })}
    </svg>
  )
}
