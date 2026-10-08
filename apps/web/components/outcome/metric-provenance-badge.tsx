import { Badge } from "@/components/ui/badge"
import type { OutcomeMeasurementKind } from "@/lib/outcome-labels"
import { cn } from "@/lib/utils"

const labels: Record<OutcomeMeasurementKind, string> = {
  estimate: "Estimate",
  operational: "Operational",
  measured: "Measured",
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
        "text-xs font-normal font-medium",
        kind === "estimate" ? "border-warning/30 text-warning" : "",
        kind === "measured" ? "border-success/30 text-success" : "",
        className,
      )}
    >
      {labels[kind]}
    </Badge>
  )
}
