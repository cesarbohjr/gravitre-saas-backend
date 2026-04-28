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

export function AutoStatusBadge({ status, className, showIcon = true }: AutoStatusBadgeProps) {
  const variantMap: Record<string, BadgeVariant> = {
    success: "success",
    completed: "success",
    active: "success",
    failed: "error",
    error: "error",
    warning: "warning",
    running: "info",
    pending: "muted",
    paused: "muted",
    draft: "muted",
  }

  const variant = variantMap[status] || "default"

  return (
    <StatusBadge 
      variant={variant} 
      dot={showIcon}
      className={className}
    >
      {status}
    </StatusBadge>
  )
}
