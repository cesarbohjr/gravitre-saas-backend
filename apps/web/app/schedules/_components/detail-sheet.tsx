"use client"

import Link from "next/link"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { Separator } from "@/components/ui/separator"
import { ArrowUpRight, CalendarClock, Clock, History } from "lucide-react"
import type { ScheduledItem } from "@/lib/schedules"
import { describeCron } from "@/lib/schedules"
import { KindBadge, formatDateTime, statusLabel, statusVariant } from "./shared"

export function ScheduleDetailSheet({
  item,
  open,
  onOpenChange,
}: {
  item: ScheduledItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-md">
        {item && (
          <>
            <SheetHeader className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <KindBadge kind={item.kind} />
                <StatusBadge variant={statusVariant(item.status)} dot>
                  {statusLabel(item.status)}
                </StatusBadge>
                {item.isSample && (
                  <StatusBadge variant="muted">Sample</StatusBadge>
                )}
              </div>
              <SheetTitle className="text-balance text-lg">{item.title}</SheetTitle>
              {item.subtitle && (
                <SheetDescription className="text-pretty">{item.subtitle}</SheetDescription>
              )}
            </SheetHeader>

            <div className="space-y-5 px-4 py-5">
              {item.cron && (
                <div className="rounded-lg border border-border bg-muted/40 p-3">
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Schedule
                  </p>
                  <p className="font-mono text-sm text-foreground">{item.cron}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{describeCron(item.cron)}</p>
                </div>
              )}

              <dl className="space-y-3">
                <TimingRow
                  icon={<CalendarClock className="h-4 w-4" />}
                  label="Next run"
                  value={formatDateTime(item.nextRunAt)}
                />
                <TimingRow
                  icon={<History className="h-4 w-4" />}
                  label="Last run"
                  value={formatDateTime(item.lastRunAt)}
                />
                {item.startedAt && (
                  <TimingRow
                    icon={<Clock className="h-4 w-4" />}
                    label="Started"
                    value={formatDateTime(item.startedAt)}
                  />
                )}
                {item.completedAt && (
                  <TimingRow
                    icon={<Clock className="h-4 w-4" />}
                    label="Completed"
                    value={formatDateTime(item.completedAt)}
                  />
                )}
              </dl>

              {typeof item.progress === "number" && (
                <div>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Progress</span>
                    <span className="font-medium text-foreground">{item.progress}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-[var(--chart-3)] transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, item.progress))}%` }}
                    />
                  </div>
                </div>
              )}

              {item.meta && Object.values(item.meta).some((v) => v != null && v !== "") && (
                <>
                  <Separator />
                  <dl className="grid grid-cols-1 gap-2">
                    {Object.entries(item.meta)
                      .filter(([, v]) => v != null && v !== "")
                      .map(([key, value]) => (
                        <div key={key} className="flex items-start justify-between gap-4 text-sm">
                          <dt className="text-muted-foreground">{key}</dt>
                          <dd className="text-right font-medium text-foreground">{String(value)}</dd>
                        </div>
                      ))}
                  </dl>
                </>
              )}

              {item.workflowId && !item.isSample && (
                <Button asChild variant="outline" className="w-full gap-2">
                  <Link href={`/workflows/${item.workflowId}`}>
                    Open workflow
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </Button>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function TimingRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="text-muted-foreground/70">{icon}</span>
        {label}
      </dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
    </div>
  )
}
