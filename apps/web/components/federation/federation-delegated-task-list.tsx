"use client"

import { useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { Check, ClipboardList, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { FederationDelegatedTask } from "@/types/api"

const STATUS_CLASS: Record<string, string> = {
  pending: "border-amber-500/30 text-amber-600",
  accepted: "border-primary/30 text-primary",
  in_progress: "border-chart-2/30 text-chart-2",
  completed: "border-emerald-500/30 text-emerald-600",
  rejected: "border-border text-muted-foreground",
  failed: "border-destructive/30 text-destructive",
  cancelled: "border-border text-muted-foreground",
}

export function FederationDelegatedTaskList({
  tasks,
  currentOrgId,
  onAction,
  onCreate,
  canCreate,
}: {
  tasks: FederationDelegatedTask[]
  currentOrgId?: string
  onAction: (action: "accept" | "reject", task: FederationDelegatedTask) => Promise<void>
  onCreate?: () => void
  canCreate?: boolean
}) {
  const [busy, setBusy] = useState<string | null>(null)

  if (tasks.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/70 px-4 py-8 text-center space-y-3">
        <p className="text-sm text-muted-foreground">
          No delegated tasks yet. Assign work to a partner once your partnership is active.
        </p>
        {canCreate && onCreate ? (
          <Button size="sm" variant="outline" onClick={onCreate}>
            <ClipboardList className="h-3.5 w-3.5 mr-1" />
            Delegate task
          </Button>
        ) : null}
      </div>
    )
  }

  async function run(action: "accept" | "reject", task: FederationDelegatedTask) {
    setBusy(`${task.id}:${action}`)
    try {
      await onAction(action, task)
    } finally {
      setBusy(null)
    }
  }

  return (
    <ul className="space-y-3">
      {tasks.map((task) => {
        const isDelegate = currentOrgId === task.delegateOrgId
        const canRespond = isDelegate && task.status === "pending"
        return (
          <li key={task.id} className="rounded-xl border border-border/70 bg-card/50 p-4 space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <ClipboardList className="h-4 w-4 text-primary shrink-0" />
                <p className="text-sm font-medium truncate">{task.title}</p>
              </div>
              <Badge variant="outline" className={cn("capitalize", STATUS_CLASS[task.status] ?? "")}>
                {task.status.replace(/_/g, " ")}
              </Badge>
            </div>
            {task.instructions ? (
              <p className="text-xs text-muted-foreground line-clamp-2">{task.instructions}</p>
            ) : null}
            {task.createdAt ? (
              <p className="text-[11px] text-muted-foreground">
                {formatDistanceToNow(new Date(task.createdAt), { addSuffix: true })}
              </p>
            ) : null}
            {canRespond ? (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void run("accept", task)}>
                  <Check className="h-3.5 w-3.5 mr-1" />
                  Accept
                </Button>
                <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => void run("reject", task)}>
                  <X className="h-3.5 w-3.5 mr-1" />
                  Decline
                </Button>
              </div>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
