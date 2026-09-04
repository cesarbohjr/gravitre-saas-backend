import { cn } from "@/lib/utils"
import { Icon, type IconName } from "@/lib/icons"
import {
  STATUS,
  STATUS_DOT,
  resolveStatusTone,
  type StatusTone,
} from "@/lib/design-system"

type BadgeVariant = "default" | "success" | "warning" | "error" | "info" | "muted"

interface StatusBadgeProps {
  variant?: BadgeVariant
  /**
   * Prefer this when the chip encodes a governance/runtime state.
   * Uses Phase 9 `--status-*` tokens via `STATUS` / `STATUS_DOT`.
   */
  tone?: StatusTone
  children: React.ReactNode
  className?: string
  dot?: boolean
  icon?: IconName
  /** Native tooltip, for when the short label needs a fuller explanation. */
  title?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-secondary text-secondary-foreground",
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  error: "bg-destructive/15 text-destructive",
  info: "bg-info/15 text-info",
  muted: "bg-muted text-muted-foreground",
}

const variantDotStyles: Record<BadgeVariant, string> = {
  default: "bg-secondary-foreground",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
  info: "bg-info",
  muted: "bg-muted-foreground",
}

/** Legacy variant → STATUS tone when callers still pass variant alone. */
const variantToTone: Partial<Record<BadgeVariant, StatusTone>> = {
  success: "approved",
  warning: "pending",
  error: "failed",
  info: "running",
  muted: "idle",
}

export function StatusBadge({
  variant = "default",
  tone,
  children,
  className,
  dot = false,
  icon,
  title,
}: StatusBadgeProps) {
  const resolvedTone = tone ?? variantToTone[variant]
  const chipClass = resolvedTone ? STATUS[resolvedTone] : variantStyles[variant]
  const dotClass = resolvedTone ? STATUS_DOT[resolvedTone] : variantDotStyles[variant]

  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        chipClass,
        className
      )}
    >
      {icon ? (
        <Icon name={icon} size="xs" />
      ) : dot ? (
        <span className={cn("h-1.5 w-1.5 rounded-full", dotClass)} />
      ) : null}
      {children}
    </span>
  )
}

interface AutoStatusBadgeProps {
  status: string
  className?: string
  showIcon?: boolean
}

/**
 * Turns a raw API status into a human label.
 *
 * Backends emit a mix of casings and separators for the same concept
 * (`COMPLETED`, `partial_success`, `in-progress`), which used to leak straight
 * into the UI as-is. Normalizing here keeps every surface consistent.
 */
export function formatStatusLabel(status: string): string {
  return status.replace(/[_-]+/g, " ").trim().toLowerCase()
}

export function AutoStatusBadge({ status, className, showIcon = true }: AutoStatusBadgeProps) {
  const tone = resolveStatusTone(status)

  return (
    <StatusBadge tone={tone} dot={showIcon} className={className}>
      {formatStatusLabel(status)}
    </StatusBadge>
  )
}
