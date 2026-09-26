"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import type { BusinessPredictionDisplay } from "@/lib/intelligence/prediction-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { Warning, TrendUp } from "@phosphor-icons/react"

const KIND_META = {
  risk: {
    icon: Warning,
    label: "Risk",
    className: "text-[color:var(--g-approval-bright)] bg-[color:var(--g-approval-soft)]",
  },
  opportunity: {
    icon: TrendUp,
    label: "Opportunity",
    className: "text-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]",
  },
  signal: {
    icon: TrendUp,
    label: "Signal",
    className: "text-muted-foreground bg-[color:var(--g-surface-2)]",
  },
} as const

export function BusinessPredictionCard({ prediction }: { prediction: BusinessPredictionDisplay }) {
  const meta = KIND_META[prediction.kind]
  const Icon = meta.icon

  return (
    <Card data-testid="business-prediction-card">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
                meta.className,
              )}
            >
              <Icon className="h-3 w-3" aria-hidden />
              {meta.label}
            </span>
            <CardTitle className="text-base font-medium leading-snug">{prediction.statement}</CardTitle>
          </div>
          {prediction.confidence != null ? (
            <ConfidenceBadge score={prediction.confidence} showScore />
          ) : null}
        </div>
        {prediction.horizon ? (
          <p className={cn(TYPE.meta, "mt-1")}>Horizon: {prediction.horizon}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        {prediction.drivers.length > 0 ? (
          <div>
            <p className={TYPE.eyebrow}>Drivers</p>
            <p>{prediction.drivers.join(" · ")}</p>
          </div>
        ) : null}
        {prediction.impact && prediction.impact !== prediction.drivers[0] ? (
          <div>
            <p className={TYPE.eyebrow}>Impact context</p>
            <p>{prediction.impact}</p>
          </div>
        ) : null}
        {prediction.evidence.length > 0 ? (
          <div>
            <p className={TYPE.eyebrow}>Evidence</p>
            <ul className="mt-1 space-y-1">
              {prediction.evidence.map((line) => (
                <li
                  key={line}
                  className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-2 py-1 text-xs"
                >
                  {line}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {prediction.actions.length > 0 ? (
          <div>
            <p className={TYPE.eyebrow}>Recommended action</p>
            <p>{prediction.actions.join("; ")}</p>
          </div>
        ) : null}
        {prediction.department ? (
          <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>
            Department: {prediction.department.replace(/_/g, " ")}
          </p>
        ) : null}
        {prediction.qualityNotes.length > 0 ? (
          <p className={cn(TYPE.meta, "text-amber-700 dark:text-amber-400")}>
            {prediction.qualityNotes.join(" · ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
