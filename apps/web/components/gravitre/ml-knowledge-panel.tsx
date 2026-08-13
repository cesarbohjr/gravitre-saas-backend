"use client"

import { Gauge, Sparkles } from "lucide-react"

export function MlKnowledgePanel() {
  return (
    <div
      className="rounded-xl border border-border/60 bg-background/50 p-4 ring-1 ring-border/40 backdrop-blur-sm"
      aria-labelledby="ml-knowledge-heading"
    >
      <div className="mb-4 flex items-center gap-2.5">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-background/70 ring-1 ring-border/50">
          <Gauge className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
        </span>
        <div>
          <h3 id="ml-knowledge-heading" className="text-sm font-semibold text-foreground">
            How your models are doing
          </h3>
          <p className="text-xs text-muted-foreground">
            Strength and trend across models you have registered.
          </p>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center">
        <Sparkles className="mb-3 h-8 w-8 text-muted-foreground/60" />
        <p className="text-sm font-medium text-foreground">No performance data yet</p>
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">
          Train or deploy a model to see strength scores and trends here.
        </p>
      </div>
    </div>
  )
}
