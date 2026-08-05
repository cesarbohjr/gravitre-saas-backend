"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { ListTodo } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"
import { HubTabs } from "@/components/gravitre/hub-tabs"

const statusConfig = {
  pending: { label: "Pending", icon: "clock", className: "" },
  processing: { label: "Processing", icon: "spinner", className: "animate-spin" },
  completed: { label: "Completed", icon: "check", className: "" },
  failed: { label: "Failed", icon: "error", className: "" },
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
  const [filter, setFilter] = useState<TaskFilter>("all")
  const { data, isLoading, mutate } = useSWR(
    user ? ["lite-tasks", user.id, filter] : null,
    () => liteApi.listTasks(filter === "all" ? undefined : { status: filter }),
    { revalidateOnFocus: false, refreshInterval: 10000 },
  )

  const handleCancel = async (id: string) => {
    try {
      await liteApi.cancelTask(id)
      toast.success("Task cancelled")
      await mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to cancel task")
    }
  }

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="My Tasks" description="Sign in to continue." icon={ListTodo}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  const tasks = data?.tasks ?? []

  return (
    <LitePageShell
      title="My Tasks"
      description="Track your AI team's progress."
      icon={ListTodo}
      loading={loading || isLoading}
      loadingLabel="Loading tasks"
      actions={
        <Link href="/lite/assign">
          <Button className="gap-2">
            <Icon name="plus" size="sm" />
            New Task
          </Button>
        </Link>
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
      <div className="space-y-3">
        {tasks.map((task) => {
          const status = statusConfig[task.status as keyof typeof statusConfig]

          return (
            <Card key={task.id} className="group border-border/50 p-4 transition-all sm:p-5">
              <div className="flex items-start gap-4">
                <div
                  className={cn(
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                    task.status === "processing" && "bg-info/10",
                    task.status === "pending" && "bg-warning/10",
                    task.status === "completed" && "bg-success/10",
                    task.status === "failed" && "bg-destructive/10",
                  )}
                >
                  <Icon
                    name={status.icon as IconName}
                    size="lg"
                    className={cn(
                      task.status === "processing" && "text-info",
                      task.status === "pending" && "text-warning",
                      task.status === "completed" && "text-success",
                      task.status === "failed" && "text-destructive",
                      status.className,
                    )}
                  />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-foreground transition-colors group-hover:text-primary">
                      {task.workflow_name}
                    </h3>
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-xs",
                        task.status === "processing" && "border-info/30 bg-info/10 text-info",
                        task.status === "pending" && "border-warning/30 bg-warning/10 text-warning",
                        task.status === "completed" &&
                          "border-success/30 bg-success/10 text-success",
                        task.status === "failed" &&
                          "border-destructive/30 bg-destructive/10 text-destructive",
                      )}
                    >
                      {status.label}
                    </Badge>
                  </div>
                  <p className="mb-3 text-sm text-muted-foreground">
                    {task.input_summary || "No input summary"}
                  </p>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Icon name="clock" size="xs" />
                      {new Date(task.created_at).toLocaleString()}
                    </span>
                  </div>

                  {(task.status === "processing" || task.status === "pending") && (
                    <div className="mt-4">
                      <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                        <div
                          className="h-full rounded-full bg-primary transition-all duration-500"
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>
                      <div className="mt-1.5 flex items-center justify-between text-xs text-muted-foreground">
                        <span>{task.progress}% complete</span>
                        {task.completed_at ? <span>Completed</span> : null}
                      </div>
                    </div>
                  )}
                </div>

                <div className="shrink-0">
                  {task.status === "completed" && (
                    <Link href="/lite/deliverables">
                      <Button size="sm" variant="outline">
                        Deliverables
                      </Button>
                    </Link>
                  )}
                  {(task.status === "processing" || task.status === "pending") && (
                    <Button size="sm" variant="outline" onClick={() => handleCancel(task.id)}>
                      Cancel
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          )
        })}
        {!tasks.length ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">No tasks yet.</Card>
        ) : null}
      </div>
    </LitePageShell>
  )
}
