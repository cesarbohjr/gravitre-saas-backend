import { cn } from "@/lib/utils"
import { Icon } from "@/lib/icons"

interface GuardrailsBoxProps {
  environment: "production" | "staging"
  approvalRules?: string[]
  adminRestrictions?: string[]
  className?: string
}

export function GuardrailsBox({
  environment,
  approvalRules = [],
  adminRestrictions = [],
  className,
}: GuardrailsBoxProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-4",
        className
      )}
    >
      <div className="mb-3 flex items-center gap-2">
        <Icon name="shield" size="sm" className="text-warning" emphasis />
        <h4 className="text-sm font-medium text-foreground">Safety Rules</h4>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Environment:</span>
          <div className="flex items-center gap-1">
            <Icon 
              name={environment === "production" ? "production" : "staging"} 
              size="xs" 
              className={environment === "production" ? "text-success" : "text-warning"}
            />
            <span
              className={cn(
                "font-medium capitalize",
                environment === "production" ? "text-success" : "text-warning"
              )}
            >
              {environment}
            </span>
          </div>
        </div>

        {approvalRules.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon name="warning" size="xs" />
              <span>Needs Approval</span>
            </div>
            <ul className="space-y-1">
              {approvalRules.map((rule, i) => (
                <li key={i} className="text-xs text-muted-foreground pl-4 flex items-start gap-2">
                  <span className="text-muted-foreground/50 mt-0.5">•</span>
                  {rule}
                </li>
              ))}
            </ul>
          </div>
        )}

        {adminRestrictions.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-1.5 text-xs text-destructive">
              <Icon name="lock" size="xs" />
              <span>Admin Only</span>
            </div>
            <ul className="space-y-1">
              {adminRestrictions.map((restriction, i) => (
                <li key={i} className="text-xs text-muted-foreground pl-4 flex items-start gap-2">
                  <span className="text-muted-foreground/50 mt-0.5">•</span>
                  {restriction}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
