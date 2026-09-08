import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { CHIP, HIGHLIGHT, type HighlightTone } from "@/lib/design-system"

/**
 * Compact Nodus soft-pill badge. Never use for invented TRAINED/certified claims —
 * only real entitlement or environment labels from callers.
 */
export function GravitreBadge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode
  tone?: HighlightTone | "brand" | "warning" | "danger" | "neutral"
  className?: string
}) {
  const highlightTone: HighlightTone =
    tone === "brand" ||
    tone === "warning" ||
    tone === "danger" ||
    tone === "neutral" ||
    tone === "signal" ||
    tone === "intelligence"
      ? tone
      : "neutral"

  return (
    <span className={cn(CHIP.compact, HIGHLIGHT[highlightTone], className)}>
      {children}
    </span>
  )
}
