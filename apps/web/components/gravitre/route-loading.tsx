import { cn } from "@/lib/utils"
import { GravitreeLoader } from "@/components/gravitre/gravitree-loader"

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
}

export function RouteLoading({ className, label = "Loading…" }: RouteLoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex min-h-[60vh] w-full flex-col items-center justify-center gap-4 p-6",
        className,
      )}
    >
      <GravitreeLoader size="lg" label={label} />
      {label ? (
        <p className="animate-pulse text-sm font-medium text-muted-foreground">{label}</p>
      ) : null}
      <span className="sr-only">{label || "Loading"}</span>
    </div>
  )
}
