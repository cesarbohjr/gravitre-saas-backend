"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { ListTodo } from "lucide-react"
import { Button } from "@/components/ui/button"
import { relativeTime } from "@/lib/agent-job-result"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"
import { HubTabs } from "@/components/gravitre/hub-tabs"

const statusConfig = {
  pending: { label: "Pending", icon: "clock", className: "" },
  processing: { label: "Processing", icon: "spinner", className: "animate-spin motion-reduce:animate-none" },
  completed: { label: "Completed", icon: "check", className: "" },
  failed: { label: "Failed", icon: "error", className: "" },
}

const STATUS_TEXT: Record<string, string> = {
  pending: "text-warning",
  processing: "text-info",
  completed: "text-success",
  failed: "text-destructive",
}

type TaskFilter = "all" | "pending" | "processing" | "completed" | "failed"

const FILTER_TABS: { id: TaskFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "pending", label: "Pending" },
  { id: "processing", label: "Processing" },
  { id: "completed", label: "Completed" },
  { id: "failed", label: "Failed" },
]

export default function LiteTasksPage() {
  const { user, loading } = useAuth()
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const [filter, setFilter] = useState<TaskFilter>("all")
  const { data, isLoading, error, mutate } = useSWR(
    user ? ["lite-tasks", user.id, filter] : null,
    () => liteApi.listTasks(filter === "all" ? undefined : { status: filter }),
    { revalidateOnFocus: false, refreshInterval: 10000 },
  )

  const handleCancel = async (id: string) => {
    if (cancellingId) return
    setCancellingId(id)
    try {
      await liteApi.cancelTask(id)
      toast.success("Task cancelled")
      await mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to cancel task")
    } finally {
      setCancellingId(null)
    }
  }

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="My tasks" description="Sign in to continue." icon={ListTodo}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  const tasks = data?.tasks ?? []

  return (
    <LitePageShell
      title="My tasks"
      description="Track your AI team's progress."
      icon={ListTodo}
      loading={loading || isLoading}
      loadingLabel="Loading tasks"
      actions={
        <Button asChild className="gap-2">
          <Link href="/lite/assign">
            <Icon name="plus" size="sm" />
            New task
          </Link>
        </Button>
      }
      headerChildren={
        <HubTabs
          tabs={FILTER_TABS}
          active={filter}
          onSelect={setFilter}
          ariaLabel="Task status filters"
          size="sm"
        />
      }
    >
      {error ? <WorkSectionErrorCard title="Could not load tasks" message={error instanceof Error ? error.message : "Try again to retrieve the latest data."} onRetry={() => void mutate()} /> : null}
      <ul className="flex flex-col divide-y divide-divide border-y border-divide">
        {tasks.map((task) => {
          const status = statusConfig[task.status as keyof typeof statusConfig] ?? { label: "Not reported", icon: "clock", className: "" }
          const isActive = task.status === "processing" || task.status === "pending"
          const showProgress = task.status === "processing" && task.progress != null && task.progress > 0
          const progress = Math.min(100, Math.max(0, task.progress ?? 0))
          const timeLabel =
            task.status === "completed" && task.completed_at
              ? `Finished ${relativeTime(task.completed_at)}`
              : `Started ${relativeTime(task.created_at)}`

          return (
            <li key={task.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:gap-6">
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex min-w-0 items-center gap-2">
                  <Icon
                    name={status.icon as IconName}
                    size="sm"
                    aria-hidden="true"
                    className={cn("shrink-0", STATUS_TEXT[task.status], status.className)}
                  />
                  <h3 className="truncate font-medium text-foreground">{task.workflow_name}</h3>
                  <span className={cn("shrink-0 text-xs font-medium", STATUS_TEXT[task.status])}>
                    {status.label}
                  </span>
                </div>
                <p className="truncate pl-6 text-sm text-muted-foreground">
                  {task.input_summary || "No input summary"}
                  <span aria-hidden="true">{" · "}</span>
                  <time dateTime={task.completed_at ?? task.created_at} title={new Date(task.completed_at ?? task.created_at).toLocaleString()}>
                    {timeLabel}
                  </time>
                </p>
                {task.status === "failed" && task.error ? (
                  <p className="pl-6 text-sm text-destructive">{task.error}</p>
                ) : null}
                {showProgress ? (
                  <div className="flex items-center gap-3 pl-6 pt-1">
                    <div
                      className="h-1 max-w-xs flex-1 overflow-hidden rounded-full bg-secondary"
                      role="progressbar"
                      aria-label={`${task.workflow_name} progress`}
                      aria-valuenow={progress}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="h-full rounded-full bg-info transition-[width] duration-200 motion-reduce:transition-none"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-muted-foreground">{progress}%</span>
                  </div>
                ) : null}
                {isActive && task.progress == null ? (
                  <p className="pl-6 text-xs text-muted-foreground">Progress not reported</p>
                ) : null}
              </div>

              <div className="flex shrink-0 pl-6 sm:pl-0">
                {task.status === "completed" && (
                  <Button asChild size="sm" variant="outline">
                    <Link href="/lite/deliverables">View deliverables</Link>
                  </Button>
                )}
                {task.status === "failed" && (
                  <Button asChild size="sm" variant="outline">
                    <Link href="/lite/assign">Assign again</Link>
                  </Button>
                )}
                {isActive && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground"
                    disabled={Boolean(cancellingId)}
                    onClick={() => handleCancel(task.id)}
                  >
                    {cancellingId === task.id ? "Cancelling…" : "Cancel"}
                  </Button>
                )}
              </div>
            </li>
          )
        })}
        {!error && !tasks.length ? (
          <li className="p-8 text-center text-sm text-muted-foreground">No tasks yet.</li>
        ) : null}
      </ul>
    </LitePageShell>
  )
}
