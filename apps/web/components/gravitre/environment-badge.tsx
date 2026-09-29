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
        "inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-[color:var(--g-text-secondary)]",
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
            environment === "production" ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-approval)]"
          )}
        />
      )}
      {environment === "production" ? "Production" : "Staging"}
    </span>
  )
}
