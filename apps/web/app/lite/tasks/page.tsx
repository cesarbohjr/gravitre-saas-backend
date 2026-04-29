"use client"

import { useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"

const statusConfig = {
  pending: { label: "Pending", icon: "clock", className: "" },
  processing: { label: "Processing", icon: "spinner", className: "animate-spin" },
  completed: { label: "Completed", color: "bg-emerald-500", icon: "check", className: "" },
  failed: { label: "Failed", color: "bg-red-500", icon: "error", className: "" },
}

export default function LiteTasksPage() {
  const { user, loading } = useAuth()
  const [filter, setFilter] = useState<string>("all")
  const { data, isLoading, mutate } = useSWR(
    user ? ["lite-tasks", user.id, filter] : null,
    () => liteApi.listTasks(filter === "all" ? undefined : { status: filter }),
    { revalidateOnFocus: false, refreshInterval: 10000 }
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

  if (loading || isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading tasks...</div>
  }
  if (!user) {
    return <div className="p-8 text-sm text-muted-foreground">Sign in required.</div>
  }

  const tasks = data?.tasks ?? []

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-foreground">My Tasks</h1>
              <p className="text-muted-foreground text-sm">Track your AI team&apos;s progress</p>
            </div>
            <Link href="/lite/assign">
              <Button className="gap-2 bg-emerald-500 hover:bg-emerald-600 text-white">
                <Icon name="plus" size="sm" />
                New Task
              </Button>
            </Link>
          </div>
          
          {/* Filters */}
          <div className="flex gap-2">
            {[
              { id: "all", label: "All" },
              { id: "pending", label: "Pending" },
              { id: "processing", label: "Processing" },
              { id: "completed", label: "Completed" },
              { id: "failed", label: "Failed" },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  filter === f.id
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tasks List */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="space-y-4">
          {tasks.map((task) => {
            const status = statusConfig[task.status as keyof typeof statusConfig]
            
            return (
              <Card key={task.id} className="p-6 border-border/50 transition-all group">
                  <div className="flex items-start gap-5">
                    {/* Status Icon */}
                    <div className={cn(
                      "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
                      task.status === "processing" && "bg-blue-500/10",
                      task.status === "pending" && "bg-amber-500/10",
                      task.status === "completed" && "bg-emerald-500/10",
                      task.status === "failed" && "bg-red-500/10"
                    )}>
                      <Icon 
                        name={status.icon as any} 
                        size="lg" 
                        className={cn(
                          task.status === "processing" && "text-blue-500",
                          task.status === "pending" && "text-amber-500",
                          task.status === "completed" && "text-emerald-500",
                          task.status === "failed" && "text-red-500",
                          status.className
                        )} 
                      />
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold text-foreground group-hover:text-emerald-500 transition-colors">
                          {task.workflow_name}
                        </h3>
                        <Badge 
                          variant="outline" 
                          className={cn(
                            "text-xs",
                            task.status === "processing" && "text-blue-500 border-blue-500/30 bg-blue-500/10",
                            task.status === "pending" && "text-amber-500 border-amber-500/30 bg-amber-500/10",
                            task.status === "completed" && "text-emerald-500 border-emerald-500/30 bg-emerald-500/10",
                            task.status === "failed" && "text-red-500 border-red-500/30 bg-red-500/10"
                          )}
                        >
                          {status.label}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-3">{task.input_summary || "No input summary"}</p>
                      
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Icon name="clock" size="xs" />
                          {new Date(task.created_at).toLocaleString()}
                        </span>
                      </div>
                      
                      {/* Progress bar for running tasks */}
                      {(task.status === "processing" || task.status === "pending") && (
                        <div className="mt-4">
                          <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-500"
                              style={{ width: `${task.progress}%` }}
                            />
                          </div>
                          <div className="flex items-center justify-between mt-1.5 text-xs text-muted-foreground">
                            <span>{task.progress}% complete</span>
                            {task.completed_at ? <span>Completed</span> : null}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Action */}
                    <div className="shrink-0">
                      {task.status === "completed" && (
                        <Link href="/lite/deliverables">
                          <Button size="sm" variant="outline">Deliverables</Button>
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
        </div>
      </div>
    </div>
  )
}
