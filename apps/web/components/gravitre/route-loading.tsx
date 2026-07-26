import { cn } from "@/lib/utils"
import { CenteredLoader, type CenteredLoaderFill } from "@/components/gravitre/gravitree-loader"

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
  /** Use `parent` when RouteLoading renders inside AppShell `<main>`. */
  fill?: CenteredLoaderFill
}

export function RouteLoading({
  className,
  label = "Loading…",
  fill = "viewport",
}: RouteLoadingProps) {
  return (
    <CenteredLoader
      size="lg"
      label={label}
      fill={fill}
      showLabel={Boolean(label)}
      className={cn(className)}
    />
  )
}
