import { cn } from "@/lib/utils"
import { LucideIcon, ExternalLink, Target } from "lucide-react"
import { EnvironmentBadge } from "./environment-badge"
import { StatusBadge } from "./status-badge"
import { Button } from "@/components/ui/button"

type ContextType = "run" | "workflow" | "connector" | "source"

interface ContextPackProps {
  type: ContextType
  title: string
  status: "active" | "completed" | "failed" | "pending" | "running"
  summary: string
  environment: "production" | "staging"
  href?: string
  icon: LucideIcon
  isActive?: boolean
  onSetActive?: () => void
  className?: string
}

const statusVariants: Record<string, "success" | "error" | "warning" | "info" | "muted"> = {
  active: "success",
  completed: "success",
  failed: "error",
  pending: "warning",
  running: "info",
}

export function ContextPack({
  type,
  title,
  status,
  summary,
  environment,
  href,
  icon: Icon,
  isActive = false,
  onSetActive,
  className,
}: ContextPackProps) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4 transition-colors",
        isActive ? "border-info bg-info/5" : "border-border",
        className
      )}
    >
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-secondary">
            <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              {type}
            </span>
          </div>
        </div>
        {href && (
          <a
            href={href}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      <h4 className="mb-2 text-sm font-medium text-foreground">{title}</h4>
      <p className="mb-3 text-xs text-muted-foreground line-clamp-2">{summary}</p>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge variant={statusVariants[status]} dot>
            {status}
          </StatusBadge>
          <EnvironmentBadge environment={environment} />
        </div>
        {onSetActive && (
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 gap-1 px-2 text-[10px]",
              isActive 
                ? "text-info hover:text-info" 
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={onSetActive}
          >
            <Target className="h-3 w-3" />
            {isActive ? "Active" : "Set active"}
          </Button>
        )}
      </div>
    </div>
  )
}
