"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { ArrowUpRight, CalendarClock, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { StatusBadge } from "@/components/gravitre/status-badge"
import {
  ScheduleEditorDialog,
  type ScheduleEditorInitial,
} from "@/components/schedules/schedule-editor-dialog"
import type { ScheduleOccurrence } from "@/lib/schedules"
import { describeCron } from "@/lib/schedules"
import {
  canDeleteScheduleItem,
  canMoveScheduleItem,
  deleteScheduledItem,
  moveScheduledItem,
  parseDateTimeLocalValue,
  parseScheduledItemIds,
  scheduleDeleteDescription,
  scheduleDeleteLabel,
  scheduleEditHref,
  scheduleEditLabel,
  scheduleMoveDescription,
  toDateTimeLocalValue,
} from "@/lib/schedules/actions"
import { KindBadge, formatDateTime, statusLabel, statusVariant } from "./shared"

export function ScheduleItemDialog({
  occurrence,
  open,
  onOpenChange,
  onUpdated,
  workflowOptions = [],
}: {
  occurrence: ScheduleOccurrence | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdated?: () => void
  workflowOptions?: Array<{ id: string; name: string }>
}) {
  const item = occurrence?.item ?? null
  const ids = useMemo(() => (item ? parseScheduledItemIds(item) : {}), [item])
  const editHref = item ? scheduleEditHref(item, ids) : null
  const canMove = item ? canMoveScheduleItem(item) : false
  const canDelete = item ? canDeleteScheduleItem(item) : false
  const canEditWorkflowSchedule =
    item?.kind === "workflow" && Boolean(item.workflowId && ids.scheduleId) && !item.isSample

  const [dateTimeValue, setDateTimeValue] = useState("")
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)
  const [isMoving, setIsMoving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (!occurrence) return
    setDateTimeValue(toDateTimeLocalValue(occurrence.date))
  }, [occurrence])

  const targetDate = parseDateTimeLocalValue(dateTimeValue)

  const editorInitial: ScheduleEditorInitial | null = canEditWorkflowSchedule
    ? {
        scheduleId: ids.scheduleId,
        workflowId: item?.workflowId,
        name: item?.name,
        scheduleType: item?.scheduleType || (item?.cron === "@once" ? "once" : "recurring"),
        cron: item?.cron,
        timezone: item?.timezone || "UTC",
        runAt: item?.runAt || item?.nextRunAt,
        endsAt: item?.endsAt,
        enabled: item?.status !== "disabled",
      }
    : null

  const handleMove = async () => {
    if (!item || !targetDate) {
      toast.error("Choose a valid date and time")
      return
    }
    setIsMoving(true)
    try {
      await moveScheduledItem(item, targetDate)
      toast.success("Schedule updated")
      onOpenChange(false)
      onUpdated?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not move schedule")
    } finally {
      setIsMoving(false)
    }
  }

  const confirmDelete = async () => {
    if (!item) return
    setIsDeleting(true)
    try {
      await deleteScheduledItem(item)
      toast.success(
        item.kind === "workflow"
          ? "Workflow schedule deleted"
          : item.kind === "task"
            ? "Scheduled task cancelled"
            : "Training job cancelled",
      )
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
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-md">
          {item && occurrence ? (
            <>
              <DialogHeader className="space-y-3 border-b border-border px-6 py-5 text-left">
                <div className="flex flex-wrap items-center gap-2">
                  <KindBadge kind={item.kind} />
                  <StatusBadge variant={statusVariant(item.status)} dot>
                    {statusLabel(item.status)}
                  </StatusBadge>
                  {item.scheduleType === "once" ? (
                    <StatusBadge variant="muted">One-time</StatusBadge>
                  ) : null}
                  {item.isSample ? <StatusBadge variant="muted">Sample</StatusBadge> : null}
                </div>
                <DialogTitle className="text-balance text-lg">{item.title}</DialogTitle>
                {item.subtitle ? (
                  <DialogDescription className="text-pretty">{item.subtitle}</DialogDescription>
                ) : null}
              </DialogHeader>

              <div className="space-y-5 px-6 py-5">
                {item.scheduleType === "once" || item.cron === "@once" ? (
                  <div className="rounded-lg border border-border bg-muted/40 p-3">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      One-time run
                    </p>
                    <p className="text-sm text-foreground">
                      {formatDateTime(item.runAt || item.nextRunAt || occurrence.date.toISOString())}
                    </p>
                    {item.timezone ? (
                      <p className="mt-1 text-xs text-muted-foreground">{item.timezone}</p>
                    ) : null}
                  </div>
                ) : item.cron ? (
                  <div className="rounded-lg border border-border bg-muted/40 p-3">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Recurrence
                    </p>
                    <p className="font-mono text-sm text-foreground">{item.cron}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{describeCron(item.cron)}</p>
                    {item.timezone ? (
                      <p className="mt-1 text-xs text-muted-foreground">Timezone: {item.timezone}</p>
                    ) : null}
                  </div>
                ) : null}

                <div className="grid gap-2 text-sm">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-muted-foreground">Shown at</span>
                    <span className="font-medium text-foreground">
                      {formatDateTime(occurrence.date.toISOString())}
                    </span>
                  </div>
                  {item.nextRunAt ? (
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">Next run</span>
                      <span className="font-medium text-foreground">{formatDateTime(item.nextRunAt)}</span>
                    </div>
                  ) : null}
                  {item.workflowId ? (
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">Workflow</span>
                      <Link
                        href={`/workflows/${item.workflowId}`}
                        className="font-medium text-primary hover:underline"
                      >
                        Open
                      </Link>
                    </div>
                  ) : null}
                </div>

                {canMove ? (
                  <div className="space-y-2 rounded-lg border border-border p-3">
                    <Label htmlFor="schedule-move-at" className="text-sm font-medium">
                      Reschedule
                    </Label>
                    <Input
                      id="schedule-move-at"
                      type="datetime-local"
                      value={dateTimeValue}
                      onChange={(event) => setDateTimeValue(event.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      {targetDate
                        ? scheduleMoveDescription(item, targetDate).replace(/\?$/, ".")
                        : "Pick a new date and time for this item."}
                    </p>
                    <Button
                      className="w-full gap-2"
                      onClick={() => void handleMove()}
                      disabled={isMoving || !targetDate}
                    >
                      <CalendarClock className="h-4 w-4" />
                      {isMoving ? "Rescheduling…" : "Reschedule"}
                    </Button>
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                    This item type cannot be moved from the calendar. Use Edit to change it on its detail page.
                  </p>
                )}

                <div className="flex flex-col gap-2">
                  {canEditWorkflowSchedule ? (
                    <Button
                      variant="outline"
                      className="w-full gap-2"
                      onClick={() => setEditorOpen(true)}
                    >
                      <Pencil className="h-4 w-4" />
                      Edit schedule
                    </Button>
                  ) : editHref ? (
                    <Button asChild variant="outline" className="w-full gap-2">
                      <Link href={editHref}>
                        {scheduleEditLabel(item)}
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

              <DialogFooter className="border-t border-border px-6 py-4">
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Close
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

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

      <ScheduleEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        workflows={workflowOptions}
        lockedWorkflowId={item?.workflowId}
        initial={editorInitial}
        onSaved={() => {
          onOpenChange(false)
          onUpdated?.()
        }}
      />
    </>
  )
}
