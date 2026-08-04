import { cn } from "@/lib/utils"
import { Icon, type IconName } from "@/lib/icons"

type BadgeVariant = "default" | "success" | "warning" | "error" | "info" | "muted"

interface StatusBadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
  dot?: boolean
  icon?: IconName
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-secondary text-secondary-foreground",
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  error: "bg-destructive/15 text-destructive",
  info: "bg-info/15 text-info",
  muted: "bg-muted text-muted-foreground",
}

const dotStyles: Record<BadgeVariant, string> = {
  default: "bg-secondary-foreground",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
  info: "bg-info",
  muted: "bg-muted-foreground",
}

export function StatusBadge({
  variant = "default",
  children,
  className,
  dot = false,
  icon,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        variantStyles[variant],
        className
      )}
    >
      {icon ? (
        <Icon name={icon} size="xs" />
      ) : dot ? (
        <span className={cn("h-1.5 w-1.5 rounded-full", dotStyles[variant])} />
      ) : null}
      {children}
    </span>
  )
}

// Convenience component for status-based badges with automatic styling
interface AutoStatusBadgeProps {
  status: string
  className?: string
  showIcon?: boolean
}

const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  success: "success",
  completed: "success",
  active: "success",
  partial_success: "warning",
  failed: "error",
  error: "error",
  cancelled: "muted",
  canceled: "muted",
  warning: "warning",
  running: "info",
  queued: "info",
  in_progress: "info",
  pending: "muted",
  paused: "muted",
  draft: "muted",
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
  // Statuses arrive in mixed casing, so normalize before mapping — otherwise
  // "COMPLETED" misses the `completed` key and silently renders as neutral.
  const key = status.trim().toLowerCase().replace(/[\s-]+/g, "_")
  const variant = STATUS_VARIANTS[key] || "default"

  return (
    <StatusBadge variant={variant} dot={showIcon} className={className}>
      {formatStatusLabel(status)}
    </StatusBadge>
  )
}
