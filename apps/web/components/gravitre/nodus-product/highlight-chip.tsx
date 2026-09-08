import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { CHIP, HIGHLIGHT, type HighlightTone } from "@/lib/design-system"

/**
 * Soft Nodus highlight pill (Product Image “GPT-4o mini” / “Llama” chips).
 * Prefer over ad-hoc emerald/blue/purple utility fills.
 */
export function HighlightChip({
  children,
  tone = "brand",
  icon,
  className,
  compact = false,
}: {
  children: ReactNode
  tone?: HighlightTone
  icon?: ReactNode
  className?: string
  compact?: boolean
}) {
  return (
    <span className={cn(compact ? CHIP.compact : CHIP.base, HIGHLIGHT[tone], className)}>
      {icon}
      {children}
    </span>
  )
}
