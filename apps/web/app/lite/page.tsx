"use client"

import Link from "next/link"
import useSWR from "swr"
import { Home } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Icon } from "@/lib/icons"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useState } from "react"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"
import { StatsGrid, StatCard } from "@/components/gravitre/page-header"

export default function LiteDashboard() {
  const { user, loading } = useAuth()
  const [taskInput, setTaskInput] = useState("")
  const { data, isLoading } = useSWR(
    user ? ["lite-home", user.id] : null,
    () => liteApi.home(),
    { revalidateOnFocus: false, refreshInterval: 15000 },
  )

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="Home" description="Sign in to continue." icon={Home}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  return (
    <LitePageShell
      title="Home"
      description="Assign work quickly and track your outputs."
      icon={Home}
      loading={loading || isLoading}
      loadingLabel="Loading Lite home"
      actions={
        <Link href={`/lite/assign${taskInput ? `?task=${encodeURIComponent(taskInput)}` : ""}`}>
          <Button className="gap-2">
            <Icon name="send" size="sm" />
            Assign
          </Button>
        </Link>
      }
    >
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          value={taskInput}
          onChange={(e) => setTaskInput(e.target.value)}
          placeholder="Describe the work to assign"
          className="sm:flex-1"
        />
        <Link href={`/lite/assign${taskInput ? `?task=${encodeURIComponent(taskInput)}` : ""}`}>
          <Button className="w-full gap-2 sm:w-auto">
            <Icon name="send" size="sm" />
            Assign
          </Button>
        </Link>
      </div>

      <StatsGrid columns={3}>
        <StatCard label="Tasks this week" value={data?.stats.tasks_this_week ?? 0} />
        <StatCard label="Completed this week" value={data?.stats.completed_this_week ?? 0} variant="success" />
        <StatCard label="Pending deliverables" value={data?.stats.pending_deliverables ?? 0} variant="warning" />
      </StatsGrid>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Quick Actions
          </h2>
          <Link href="/lite/assign" className="text-xs text-muted-foreground hover:text-foreground">
            Open assign
          </Link>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {(data?.quick_actions ?? []).map((action) => (
            <Link key={action.id} href={`/lite/assign?workflowId=${action.workflow_id}`}>
              <Card className="p-4 transition-colors hover:border-foreground/30">
                <p className="font-medium">{action.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {action.description || "Run workflow"}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium">Recent Tasks</h3>
            <Link href="/lite/tasks" className="text-xs text-muted-foreground hover:text-foreground">
              View all
            </Link>
          </div>
          <div className="space-y-2">
            {(data?.recent_tasks ?? []).map((task) => (
              <div key={task.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{task.workflow_name}</p>
                  <Badge variant="outline">{task.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {task.input_summary || "No summary"}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium">Pending Deliverables</h3>
            <Link
              href="/lite/deliverables"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all
            </Link>
          </div>
          <div className="space-y-2">
            {(data?.pending_deliverables ?? []).map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <p className="text-sm font-medium">{item.name}</p>
                <p className="text-xs text-muted-foreground">{item.type}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </LitePageShell>
  )
}
