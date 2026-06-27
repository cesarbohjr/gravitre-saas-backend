"use client"

import { cn } from "@/lib/utils"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { CalendarClock, History } from "lucide-react"
import type { ScheduledItem } from "@/lib/schedules"
import { KindBadge, formatDateTime, statusLabel, statusVariant } from "./shared"

export function ListView({
  items,
  selectedId,
  onSelect,
  onOpen,
}: {
  items: ScheduledItem[]
  selectedId?: string
  onSelect: (item: ScheduledItem) => void
  onOpen: (item: ScheduledItem) => void
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="hidden border-b border-border bg-muted/40 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground md:grid md:grid-cols-[1.6fr_0.8fr_1fr_1fr_0.7fr] md:gap-4">
        <span>Item</span>
        <span>Type</span>
        <span>Next run</span>
        <span>Last run</span>
        <span>Status</span>
      </div>
      <ul className="divide-y divide-border">
        {items.map((item) => {
          const selected = item.id === selectedId
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item)}
                onDoubleClick={() => onOpen(item)}
                title="Double-click for details"
                className={cn(
                  "grid w-full grid-cols-1 gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/50 md:grid-cols-[1.6fr_0.8fr_1fr_1fr_0.7fr] md:items-center md:gap-4",
                  selected && "bg-muted",
                )}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <span
                    className="h-8 w-1 shrink-0 rounded-full"
                    style={{
                      backgroundColor:
                        item.kind === "workflow"
                          ? "var(--chart-1)"
                          : item.kind === "task"
                            ? "var(--chart-2)"
                            : "var(--chart-3)",
                    }}
                  />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{item.title}</p>
                    {item.subtitle && (
                      <p className="truncate text-xs text-muted-foreground">{item.subtitle}</p>
                    )}
                  </div>
                </div>

                <div className="md:block">
                  <KindBadge kind={item.kind} />
                </div>

                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <CalendarClock className="h-3.5 w-3.5 shrink-0 md:hidden" />
                  <span className="md:hidden">Next:</span>
                  {formatDateTime(item.nextRunAt)}
                </div>

                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <History className="h-3.5 w-3.5 shrink-0 md:hidden" />
                  <span className="md:hidden">Last:</span>
                  {formatDateTime(item.lastRunAt)}
                </div>

                <div className="flex items-center gap-2">
                  <StatusBadge variant={statusVariant(item.status)} dot>
                    {statusLabel(item.status)}
                  </StatusBadge>
                  {item.isSample && <StatusBadge variant="muted">Sample</StatusBadge>}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
