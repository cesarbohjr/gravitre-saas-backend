import { Info } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  OPERATIONAL_METHODOLOGY,
  OPTIMIZATION_ESTIMATE_METHODOLOGY,
  ROI_METHODOLOGY,
  OUTCOME_LABELING_SUMMARY,
} from "@/lib/outcome-labels"

type Variant = "estimate" | "operational" | "optimization" | "summary"

const copy: Record<Variant, string> = {
  estimate: ROI_METHODOLOGY,
  operational: OPERATIONAL_METHODOLOGY,
  optimization: OPTIMIZATION_ESTIMATE_METHODOLOGY,
  summary: OUTCOME_LABELING_SUMMARY,
}

export function OutcomeMethodologyCallout({
  variant = "summary",
  className,
}: {
  variant?: Variant
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex gap-2 rounded-lg border border-border/80 bg-muted/30 px-3 py-2 text-xs text-muted-foreground",
        className,
      )}
    >
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/80" aria-hidden />
      <p>{copy[variant]}</p>
    </div>
  )
}
