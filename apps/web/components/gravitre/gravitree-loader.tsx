"use client"

import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"
import { cn } from "@/lib/utils"

export type GravitreeLoaderSize = "xs" | "sm" | "md" | "lg"

/** Pixel sizes for the shared 200×200 brand SVG (square, not the old wide bars). */
const sizeMap: Record<GravitreeLoaderSize, number> = {
  xs: 28,
  sm: 36,
  md: 48,
  lg: 72,
}

export interface GravitreeLoaderProps {
  size?: GravitreeLoaderSize
  className?: string
  label?: string
}

/**
 * Single Gravitre page/async loader — the gooey two-bar mark with the morphing
 * ellipse (`ry`/`rx` SMIL animation). Same artwork as chat “thinking”.
 */
export function GravitreeLoader({
  size = "md",
  className,
  label = "Loading",
}: GravitreeLoaderProps) {
  return (
    <GravitreThinkingLoader
      size={sizeMap[size]}
      className={cn("text-foreground", className)}
      title={label}
    />
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
