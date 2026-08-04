"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import type { Agent } from "@/types/api"
import { Badge } from "@/components/ui/badge"

export function HealthTab({ agent, enabled }: { agent: Agent; enabled: boolean }) {
  if (!enabled) return null

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "active":
        return "bg-success/10 text-success border-success/20"
      case "degraded":
        return "bg-warning/10 text-warning border-warning/20"
      default:
        return "bg-muted text-muted-foreground border-border"
    }
  }

  const toolsCount = Array.isArray(agent.capabilities) ? agent.capabilities.length : 0

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant="outline" className={getStatusColor(agent.status)}>
            {agent.status.toUpperCase()}
          </Badge>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Execution Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <ExecutionModeBadge source={{ execution_mode: "advisory_only" }} showMeta />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Connected Tools</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{toolsCount}</div>
        </CardContent>
      </Card>

      <Card className="sm:col-span-2 lg:col-span-3">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Last Task</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-foreground">{agent.lastAction || "No recent activity"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{agent.lastActionTime}</p>
        </CardContent>
      </Card>
    </div>
  )
}
