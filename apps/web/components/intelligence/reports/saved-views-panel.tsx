"use client"

import { Button } from "@/components/ui/button"
import { RADIUS, TYPE } from "@/lib/design-system"
import {
  REPORT_TEMPLATES,
  type SavedIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { cn } from "@/lib/utils"

export function SavedViewsPanel({
  views,
  currentLabel,
  canSave,
  onSave,
  onLoad,
  onRemove,
}: {
  views: SavedIntelligenceView[]
  currentLabel: string
  canSave: boolean
  onSave: () => void
  onLoad: (view: SavedIntelligenceView) => void
  onRemove: (id: string) => void
}) {
  const saveTitle = canSave ? undefined : "Pick an organization first. Views are saved per organization."
  return (
    <section
      aria-labelledby="reports-saved-heading"
      className={cn(RADIUS.panel, "border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 sm:p-6")}
    >
      <h2 id="reports-saved-heading" className={cn(TYPE.cardTitle, "text-lg")}>
        Saved views
      </h2>
      {views.length === 0 ? (
        <div className={cn(RADIUS.card, "mt-4 border border-dashed border-[color:var(--g-border-default)] p-4 sm:p-5")}>
          <p className="text-sm font-semibold text-[color:var(--g-text-primary)]">Nothing saved yet</p>
          <p className={cn(TYPE.bodyMuted, "mt-1.5")}>
            Save the template and period you&apos;re looking at to come back to it. Views are kept on this device.
          </p>
          <Button className="mt-3" size="sm" onClick={onSave} disabled={!canSave} title={saveTitle}>
            Save {currentLabel}
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <ul className="space-y-2">
            {views.map((view) => {
              const template = REPORT_TEMPLATES.find((t) => t.id === view.templateId)?.label ?? "Report"
              return (
                <li
                  key={view.id}
                  className={cn(
                    RADIUS.card,
                    "flex flex-wrap items-center justify-between gap-2 border border-[color:var(--g-border-subtle)] px-3 py-2",
                  )}
                >
                  <button
                    type="button"
                    className="min-h-11 min-w-0 text-left text-sm font-medium text-[color:var(--g-text-primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-0"
                    onClick={() => onLoad(view)}
                    aria-label={`Open saved view ${template}, last ${view.periodDays} days`}
                  >
                    {template} · {view.periodDays} days
                    <span className={cn(TYPE.meta, "ml-2 font-normal")}>
                      Saved {new Date(view.savedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="min-h-11 text-xs text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-0"
                    onClick={() => onRemove(view.id)}
                    aria-label={`Remove saved view ${template}, last ${view.periodDays} days`}
                  >
                    Remove
                  </button>
                </li>
              )
            })}
          </ul>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={onSave} disabled={!canSave} title={saveTitle}>
              Save {currentLabel}
            </Button>
            <span className={TYPE.meta}>Kept on this device.</span>
          </div>
        </div>
      )}
    </section>
  )
}
