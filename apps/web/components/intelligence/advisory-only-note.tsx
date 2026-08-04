import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/**
 * The single source of truth for the "advisory only" guarantee.
 *
 * This one claim was previously rendered five different ways across the
 * intelligence surfaces — with four different copy strings (two of which leaked
 * the raw `advisory_only` enum straight to users) and the same hardcoded amber
 * classes copy-pasted each time. Since it's a product *promise* about whether
 * the system can act on its own, it needs to read identically everywhere.
 *
 * Uses the semantic `--warning` token rather than raw amber so it adapts per
 * theme instead of relying on `dark:` overrides.
 */

const ADVISORY_COPY = {
  short: "Advisory only",
  full: "Advisory only — human approval is required before any write action executes.",
  visibility: "Advisory only — visibility signals do not auto-execute changes.",
} as const

export type AdvisoryTone = keyof typeof ADVISORY_COPY

export function AdvisoryOnlyNote({
  tone = "short",
  variant = "badge",
  className,
}: {
  /** Which phrasing to use. All describe the same guarantee. */
  tone?: AdvisoryTone
  /** `badge` for an inline chip, `note` for a callout block. */
  variant?: "badge" | "note"
  className?: string
}) {
  const label = ADVISORY_COPY[tone]

  if (variant === "note") {
    return (
      <p
        className={cn(
          "rounded-lg border border-dashed border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning",
          className
        )}
      >
        {label}
      </p>
    )
  }

  return (
    <Badge
      variant="outline"
      className={cn("border-warning/30 bg-warning/5 font-normal text-warning", className)}
    >
      {label}
    </Badge>
  )
}
