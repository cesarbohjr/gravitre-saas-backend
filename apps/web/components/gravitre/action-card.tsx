import { cn } from "@/lib/utils"
import { EnvironmentBadge } from "./environment-badge"
import { StatusBadge } from "./status-badge"
import { Icon, type IconName } from "@/lib/icons"

interface ActionCardProps {
  title: string
  description?: string
  icon: IconName
  environment: "production" | "staging"
  requiresApproval?: boolean
  requiresAdmin?: boolean
  requiresConfirmation?: boolean
  onClick?: () => void
  className?: string
}

export function ActionCard({
  title,
  description,
  icon,
  environment,
  requiresApproval = false,
  requiresAdmin = false,
  requiresConfirmation = false,
  onClick,
  className,
}: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex w-full flex-col gap-3 rounded-lg border border-border bg-card p-4 text-left transition-all hover:border-muted-foreground/40 hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/80 transition-colors group-hover:bg-secondary">
          <Icon name={icon} size="lg" className="text-foreground" />
        </div>
        <Icon 
          name="caretRight" 
          size="sm" 
          className="text-muted-foreground/50 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5" 
        />
      </div>

      <div className="space-y-1">
        <h3 className="text-sm font-medium text-foreground group-hover:text-foreground/90">{title}</h3>
        {description && (
          <p className="text-xs text-muted-foreground/80 line-clamp-2">{description}</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <EnvironmentBadge environment={environment} />
        {requiresApproval && (
          <StatusBadge variant="warning" className="gap-1">
            <Icon name="shield" size="xs" />
            Approval
          </StatusBadge>
        )}
        {requiresAdmin && (
          <StatusBadge variant="error" className="gap-1">
            <Icon name="lock" size="xs" />
            Admin
          </StatusBadge>
        )}
        {requiresConfirmation && (
          <StatusBadge variant="info" className="gap-1">
            <Icon name="info" size="xs" />
            Confirm
          </StatusBadge>
        )}
      </div>
    </button>
  )
}
