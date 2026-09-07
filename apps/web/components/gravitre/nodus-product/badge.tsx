import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Compact Nodus-density badge. Never use for invented TRAINED/certified claims —
 * only real entitlement or environment labels from callers.
 */
export function GravitreBadge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode
  tone?: "neutral" | "brand" | "warning" | "danger"
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--np-radius-sm)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        tone === "neutral" &&
          "border border-divide bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)]",
        tone === "brand" &&
          "border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
        tone === "warning" && "border border-amber-300/60 bg-amber-500/10 text-amber-800",
        tone === "danger" &&
          "border border-destructive/30 bg-destructive/10 text-destructive",
        className,
      )}
    >
      {children}
    </span>
  )
}
