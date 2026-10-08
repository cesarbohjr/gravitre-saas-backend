import { Illustration, type IllustrationName } from "@/components/gravitre/illustration"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { GravitreSurface } from "./metric"

/**
 * Honest empty state — no fabricated metrics or demo rows.
 */
export function GravitreEmpty({
  title,
  hint,
  action,
  icon,
  illustration,
  className,
}: {
  title: string
  hint?: string
  action?: ReactNode
  icon?: ReactNode
  /** Library scene shown instead of the icon tile. */
  illustration?: IllustrationName
  className?: string
}) {
  return (
    <GravitreSurface
      className={cn("flex flex-col items-center px-4 py-10 text-center", className)}
    >
      {illustration ? (
        <Illustration name={illustration} width={160} className="mb-4" />
      ) : icon ? (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)]">
          {icon}
        </div>
      ) : null}
      <p className="text-sm font-semibold text-[color:var(--g-text-primary)]">{title}</p>
      {hint ? (
        <p className="mt-1 max-w-sm text-xs text-[color:var(--g-text-muted)]">{hint}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </GravitreSurface>
  )
}
