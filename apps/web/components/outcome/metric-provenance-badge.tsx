import { Badge } from "@/components/ui/badge"
import type { OutcomeMeasurementKind } from "@/lib/outcome-labels"
import { cn } from "@/lib/utils"

const labels: Record<OutcomeMeasurementKind, string> = {
  estimate: "Estimate",
  operational: "Operational",
}

export function MetricProvenanceBadge({
  kind,
  className,
}: {
  kind: OutcomeMeasurementKind
  className?: string
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] font-normal uppercase tracking-wide",
        kind === "estimate" ? "border-amber-500/30 text-amber-600 dark:text-amber-400" : "",
        className,
      )}
    >
      {labels[kind]}
    </Badge>
  )
}
