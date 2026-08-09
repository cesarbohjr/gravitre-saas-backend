"use client"

import type { ReactNode } from "react"

import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"
import { cn } from "@/lib/utils"

export type GravitreLoaderSize = "xs" | "sm" | "md" | "lg"

/** How the loader shell fills space — viewport = full screen; parent = AppShell main. */
export type CenteredLoaderFill = "viewport" | "parent"

/** Pixel sizes for the shared 200×200 brand SVG (square, not the old wide bars). */
const sizeMap: Record<GravitreLoaderSize, number> = {
  xs: 28,
  sm: 36,
  md: 48,
  lg: 72,
}

export interface GravitreLoaderProps {
  size?: GravitreLoaderSize
  className?: string
  label?: string
}

/**
 * Single Gravitre page/async loader — the gooey two-bar mark with the morphing
 * ellipse (`ry`/`rx` SMIL animation). Same artwork as chat “thinking”.
 */
export function GravitreLoader({
  size = "md",
  className,
  label = "Loading",
}: GravitreLoaderProps) {
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
  size?: GravitreLoaderSize
  className?: string
  label?: string
}) {
  return <GravitreLoader size={size} className={className} label={label ?? "Loading"} />
}

const centeredLoaderFillClasses: Record<CenteredLoaderFill, string> = {
  /** Route transitions and auth bootstrap — center in the full viewport. */
  viewport: "min-h-[100dvh] w-full bg-background",
  /** Inside AppShell `<main>` — expand to remaining height below the top bar. */
  parent: "min-h-0 w-full flex-1",
}

/**
 * Shared flex shell so the gooey loader stays visually centered on every surface.
 */
export function CenteredLoader({
  size = "lg",
  label = "Loading",
  fill = "viewport",
  className,
  showLabel = false,
  children,
}: {
  size?: GravitreLoaderSize
  label?: string
  fill?: CenteredLoaderFill
  className?: string
  /** When true, renders a visible caption under the mark (route loading). */
  showLabel?: boolean
  children?: ReactNode
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn(
        "flex flex-col items-center justify-center gap-4 p-6",
        centeredLoaderFillClasses[fill],
        className,
      )}
    >
      {children ?? <GravitreLoader size={size} label={label} />}
      {showLabel && label ? (
        <p className="animate-pulse text-sm font-medium text-muted-foreground">{label}</p>
      ) : null}
      <span className="sr-only">{label}</span>
    </div>
  )
}
