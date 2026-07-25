import { cn } from "@/lib/utils"
import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"

/**
 * Layout hint kept for backwards compatibility: all `loading.tsx` files pass a
 * `variant`, but every route now shows the same branded gooey loader so page
 * transitions feel consistent across the app.
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
      <GravitreThinkingLoader size={72} title={label} />
      {label ? (
        <p className="animate-pulse text-sm font-medium text-muted-foreground">{label}</p>
      ) : null}
      <span className="sr-only">{label || "Loading"}</span>
    </div>
  )
}
