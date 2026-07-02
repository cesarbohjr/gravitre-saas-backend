"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { Separator } from "@/components/ui/separator"
import { ArrowUpRight, CalendarClock, Clock, History, Pencil, Trash2 } from "lucide-react"
import type { ScheduledItem } from "@/lib/schedules"
import { describeCron } from "@/lib/schedules"
import {
  cronForDateTime,
  parseScheduledItemIds,
  scheduleDeleteDescription,
  scheduleDeleteLabel,
} from "@/lib/schedules/actions"
import { workflowsApi, runsApi } from "@/lib/api"
import { KindBadge, formatDateTime, statusLabel, statusVariant } from "./shared"

export function ScheduleDetailSheet({
  item,
  open,
  onOpenChange,
  onUpdated,
}: {
  item: ScheduledItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdated?: () => void
}) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editingCron, setEditingCron] = useState(false)
  const [cronDraft, setCronDraft] = useState("")

  const ids = useMemo(() => (item ? parseScheduledItemIds(item) : {}), [item])
  const canEdit = Boolean(item && item.kind === "workflow" && item.workflowId && ids.scheduleId && !item.isSample)
  const canDelete = Boolean(item && !item.isSample && (ids.scheduleId || ids.runId))

  const beginEdit = () => {
    if (!item?.cron) return
    setCronDraft(item.cron)
    setEditingCron(true)
  }

  const saveCron = async () => {
    if (!item?.workflowId || !ids.scheduleId || !cronDraft.trim()) return
    setIsSaving(true)
    try {
      await workflowsApi.updateSchedule(item.workflowId, ids.scheduleId, {
        cron_expression: cronDraft.trim(),
        enabled: item.status !== "disabled",
      })
      toast.success("Schedule updated")
      setEditingCron(false)
      onUpdated?.()
    } catch {
      toast.error("Could not update schedule")
    } finally {
      setIsSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!item) return
    setIsDeleting(true)
    try {
      if (item.kind === "workflow" && item.workflowId && ids.scheduleId) {
        await workflowsApi.deleteSchedule(item.workflowId, ids.scheduleId)
        toast.success("Workflow schedule deleted")
      } else if (item.kind === "task" && ids.runId) {
        await runsApi.cancel(ids.runId)
        toast.success("Scheduled task cancelled")
      } else {
        toast.error("This item cannot be deleted from the calendar")
        return
      }
      setDeleteOpen(false)
      onOpenChange(false)
      onUpdated?.()
    } catch {
      toast.error("Could not remove scheduled item")
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <>
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
                  {item.isSample ? <StatusBadge variant="muted">Sample</StatusBadge> : null}
                </div>
                <SheetTitle className="text-balance text-lg">{item.title}</SheetTitle>
                {item.subtitle ? (
                  <SheetDescription className="text-pretty">{item.subtitle}</SheetDescription>
                ) : null}
              </SheetHeader>

              <div className="space-y-5 px-4 py-5">
                {item.cron ? (
                  <div className="rounded-lg border border-border bg-muted/40 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Schedule
                      </p>
                      {canEdit ? (
                        <Button variant="ghost" size="sm" className="h-7 gap-1.5 px-2" onClick={beginEdit}>
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </Button>
                      ) : null}
                    </div>
                    {editingCron ? (
                      <div className="space-y-2">
                        <Input
                          value={cronDraft}
                          onChange={(event) => setCronDraft(event.target.value)}
                          className="font-mono text-sm"
                          aria-label="Cron expression"
                        />
                        <p className="text-xs text-muted-foreground">{describeCron(cronDraft)}</p>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => void saveCron()} disabled={isSaving}>
                            Save
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setEditingCron(false)}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="font-mono text-sm text-foreground">{item.cron}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{describeCron(item.cron)}</p>
                      </>
                    )}
                  </div>
                ) : null}

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
                  {item.startedAt ? (
                    <TimingRow
                      icon={<Clock className="h-4 w-4" />}
                      label="Started"
                      value={formatDateTime(item.startedAt)}
                    />
                  ) : null}
                  {item.completedAt ? (
                    <TimingRow
                      icon={<Clock className="h-4 w-4" />}
                      label="Completed"
                      value={formatDateTime(item.completedAt)}
                    />
                  ) : null}
                </dl>

                {typeof item.progress === "number" ? (
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
                ) : null}

                {item.meta && Object.values(item.meta).some((v) => v != null && v !== "") ? (
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
                ) : null}

                <div className="flex flex-col gap-2">
                  {item.workflowId && !item.isSample ? (
                    <Button asChild variant="outline" className="w-full gap-2">
                      <Link href={`/workflows/${item.workflowId}`}>
                        Open workflow
                        <ArrowUpRight className="h-4 w-4" />
                      </Link>
                    </Button>
                  ) : null}
                  {canDelete ? (
                    <Button
                      variant="destructive"
                      className="w-full gap-2"
                      onClick={() => setDeleteOpen(true)}
                    >
                      <Trash2 className="h-4 w-4" />
                      {scheduleDeleteLabel(item)}
                    </Button>
                  ) : null}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{item ? scheduleDeleteLabel(item) : "Delete schedule"}</AlertDialogTitle>
            <AlertDialogDescription>
              {item ? scheduleDeleteDescription(item) : "This action cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Keep schedule</AlertDialogCancel>
            <AlertDialogAction
              disabled={isDeleting}
              onClick={(event) => {
                event.preventDefault()
                void confirmDelete()
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Removing…" : "Confirm delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
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

export async function moveScheduledItem(
  item: ScheduledItem,
  targetDate: Date,
): Promise<void> {
  const ids = parseScheduledItemIds(item)
  if (item.isSample) {
    throw new Error("Sample schedules cannot be moved")
  }
  if (item.kind === "workflow" && item.workflowId && ids.scheduleId) {
    await workflowsApi.updateSchedule(item.workflowId, ids.scheduleId, {
      cron_expression: cronForDateTime(targetDate),
      enabled: item.status !== "disabled",
    })
    return
  }
  if (item.kind === "task" && ids.runId) {
    if (!["scheduled", "queued", "pending"].includes(item.status)) {
      throw new Error("Only pending tasks can be moved")
    }
    await runsApi.cancel(ids.runId)
    throw new Error("Create a new schedule from the workflow to run this task at the new time.")
  }
  throw new Error("This schedule type cannot be moved from the calendar")
}
