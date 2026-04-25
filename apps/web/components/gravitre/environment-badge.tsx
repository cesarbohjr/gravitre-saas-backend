import { cn } from "@/lib/utils"
import { Icon } from "@/lib/icons"

interface EnvironmentBadgeProps {
  environment: "production" | "staging"
  className?: string
  showIcon?: boolean
}

export function EnvironmentBadge({ environment, className, showIcon = false }: EnvironmentBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        environment === "production"
          ? "bg-success/15 text-success"
          : "bg-warning/15 text-warning",
        className
      )}
    >
      {showIcon ? (
        <Icon 
          name={environment === "production" ? "production" : "staging"} 
          size="xs" 
        />
      ) : (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            environment === "production" ? "bg-success" : "bg-warning"
          )}
        />
      )}
      {environment}
    </span>
  )
}
