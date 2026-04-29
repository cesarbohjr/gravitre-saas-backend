"use client"

import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Icon } from "@/lib/icons"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useState } from "react"

export default function LiteDashboard() {
  const { user, loading } = useAuth()
  const [taskInput, setTaskInput] = useState("")
  const { data, isLoading } = useSWR(
    user ? ["lite-home", user.id] : null,
    () => liteApi.home(),
    { revalidateOnFocus: false, refreshInterval: 15000 }
  )

  if (loading || isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading Lite dashboard...</div>
  }
  if (!user) {
    return <div className="p-8 text-sm text-muted-foreground">Sign in required.</div>
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="border rounded-xl p-5 bg-card">
          <h1 className="text-2xl font-bold">Lite Home</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Assign work quickly and track your outputs.
          </p>
          <div className="mt-4 flex gap-2">
            <Input
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              placeholder="Describe the work to assign"
            />
            <Link href={`/lite/assign${taskInput ? `?task=${encodeURIComponent(taskInput)}` : ""}`}>
              <Button className="gap-2">
                <Icon name="send" size="sm" />
                Assign
              </Button>
            </Link>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <Card className="p-4">
            <p className="text-xs text-muted-foreground">Tasks This Week</p>
            <p className="text-2xl font-semibold">{data?.stats.tasks_this_week ?? 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-muted-foreground">Completed This Week</p>
            <p className="text-2xl font-semibold">{data?.stats.completed_this_week ?? 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-muted-foreground">Pending Deliverables</p>
            <p className="text-2xl font-semibold">{data?.stats.pending_deliverables ?? 0}</p>
          </Card>
        </div>

        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Quick Actions
            </h2>
            <Link href="/lite/assign" className="text-xs text-muted-foreground">
              Open assign
            </Link>
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            {(data?.quick_actions ?? []).map((action) => (
              <Link key={action.id} href={`/lite/assign?workflowId=${action.workflow_id}`}>
                <Card className="p-4 hover:border-foreground/30 transition-colors">
                  <p className="font-medium">{action.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">{action.description || "Run workflow"}</p>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">Recent Tasks</h3>
              <Link href="/lite/tasks" className="text-xs text-muted-foreground">
                View all
              </Link>
            </div>
            <div className="space-y-2">
              {(data?.recent_tasks ?? []).map((task) => (
                <div key={task.id} className="border rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-sm">{task.workflow_name}</p>
                    <Badge variant="outline">{task.status}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{task.input_summary || "No summary"}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">Pending Deliverables</h3>
              <Link href="/lite/deliverables" className="text-xs text-muted-foreground">
                View all
              </Link>
            </div>
            <div className="space-y-2">
              {(data?.pending_deliverables ?? []).map((item) => (
                <div key={item.id} className="border rounded-lg p-3">
                  <p className="font-medium text-sm">{item.name}</p>
                  <p className="text-xs text-muted-foreground">{item.type}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
