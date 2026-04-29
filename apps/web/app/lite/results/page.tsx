"use client"

import { useState } from "react"
import useSWR from "swr"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

export default function LiteResultsPage() {
  const { user, loading } = useAuth()
  const [range, setRange] = useState("30d")
  const { data, isLoading } = useSWR(
    user ? ["lite-results", user.id, range] : null,
    () => liteApi.getResults(range),
    { revalidateOnFocus: false, refreshInterval: 20000 }
  )

  if (loading || isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading results...</div>
  }
  if (!user) {
    return <div className="p-8 text-sm text-muted-foreground">Sign in required.</div>
  }

  const summary = data?.summary

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <h1 className="text-2xl font-bold text-foreground">Results</h1>
          <p className="text-muted-foreground text-sm">Track your AI team&apos;s performance</p>
          <div className="flex gap-2 mt-4">
            {["7d", "30d", "90d"].map((option) => (
              <Button
                key={option}
                variant={range === option ? "default" : "outline"}
                size="sm"
                onClick={() => setRange(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {[
            { label: "Tasks Completed", value: summary?.tasks_completed ?? 0 },
            { label: "Success Rate", value: `${summary?.success_rate ?? 0}%` },
            { label: "Avg Completion (hrs)", value: summary?.avg_completion_time_hours ?? 0 },
            { label: "Workflows Used", value: summary?.by_workflow.length ?? 0 },
          ].map((stat) => (
            <Card 
              key={stat.label}
              className="p-5 border-border/50"
            >
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">{stat.label}</p>
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-3xl font-bold text-foreground">{stat.value}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Recent Results Timeline */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-6">
            Results by Workflow
          </h2>

          <div className="grid md:grid-cols-2 gap-3">
            {(summary?.by_workflow ?? []).map((item) => (
              <Card key={item.workflow_name} className="p-4 border-border/50">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{item.workflow_name}</p>
                  <Badge variant="outline">{item.count}</Badge>
                </div>
              </Card>
            ))}
          </div>
        </div>

        <div className="mt-10">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Recent Tasks
          </h2>
          <div className="space-y-2">
            {(data?.recent ?? []).map((task) => (
              <Card key={task.id} className="p-3 border-border/50">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-sm">{task.workflow_name}</p>
                  <Badge variant="outline">{task.status}</Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{task.input_summary || "No summary"}</p>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
