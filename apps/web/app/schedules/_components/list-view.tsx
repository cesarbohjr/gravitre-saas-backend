"use client"

import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { CalendarClock, History } from "lucide-react"
import { KIND_STYLES, type ScheduledItem } from "@/lib/schedules"
import { KindBadge, formatDateTime, scheduleBoardStyle, statusLabel, statusVariant } from "./shared"

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
  const reduceMotion = useReducedMotion()
  return (
    <div
      className="flex flex-col overflow-hidden rounded-xl border border-border bg-card"
      style={scheduleBoardStyle}
    >
      {/* Header */}
      <div className="hidden shrink-0 border-b border-border bg-muted/40 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground md:grid md:grid-cols-[1.6fr_0.8fr_1fr_1fr_0.7fr] md:gap-4">
        <span>Item</span>
        <span>Type</span>
        <span>Next run</span>
        <span>Last run</span>
        <span>Status</span>
      </div>
      <ul className="min-h-0 flex-1 divide-y divide-border overflow-y-auto">
        {items.length === 0 ? (
          <li className="flex h-full min-h-[12rem] items-center justify-center px-6 py-12 text-center text-sm text-muted-foreground">
            No scheduled items match the current filters.
          </li>
        ) : null}
        {items.map((item, index) => {
          const selected = item.id === selectedId
          return (
            <motion.li
              key={item.id}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: Math.min(index * 0.025, 0.3), ease: "easeOut" }}
            >
              <button
                type="button"
                onClick={() => onOpen(item)}
                title="Click to reschedule or edit"
                className={cn(
                  "group grid w-full grid-cols-1 gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/50 md:grid-cols-[1.6fr_0.8fr_1fr_1fr_0.7fr] md:items-center md:gap-4",
                  selected && "bg-muted",
                )}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <span
                    className="h-8 w-1 shrink-0 rounded-full transition-all group-hover:h-9"
                    style={{ backgroundColor: KIND_STYLES[item.kind].color }}
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
            </motion.li>
          )
        })}
      </ul>
    </div>
  )
}
