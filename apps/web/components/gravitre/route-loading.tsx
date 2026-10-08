"use client"

import { cn } from "@/lib/utils"
import { CenteredLoader, type CenteredLoaderFill } from "@/components/gravitre/gravitre-loader"
import { useInsideAppShell } from "@/components/gravitre/app-shell-context"

/**
 * Layout hint kept for backwards compatibility: all `loading.tsx` files pass a
 * `variant`, but every route shows the same branded gooey loader (one SVG —
 * morphing bars + ellipse) so page transitions stay consistent.
 */
export type RouteLoadingVariant = "dashboard" | "table" | "detail" | "chat"

type RouteLoadingProps = {
  variant?: RouteLoadingVariant
  className?: string
  /** Optional label under the loader. */
  label?: string
  /**
   * `parent` fills the AppShell `<main>`; `viewport` fills the screen. Defaults
   * to `parent` under the persistent shell (route-group `loading.tsx` renders
   * inside it, with the sidebar and top bar still visible) and `viewport`
   * elsewhere.
   */
  fill?: CenteredLoaderFill
}

export function RouteLoading({
  className,
  label = "Loading…",
  fill,
}: RouteLoadingProps) {
  const insideShell = useInsideAppShell()
  return (
    <CenteredLoader
      size="lg"
      label={label}
      fill={fill ?? (insideShell ? "parent" : "viewport")}
      showLabel={Boolean(label)}
      className={cn(className)}
    />
  )
}
