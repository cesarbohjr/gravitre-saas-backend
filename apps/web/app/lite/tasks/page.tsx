"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import Link from "next/link"

const tasks = [
  {
    id: "1",
    title: "Q3 Healthcare Campaign",
    description: "Create a campaign targeting mid-market healthcare companies",
    agent: "Marketing Agent",
    status: "running",
    progress: 65,
    eta: "2 min",
    outputs: ["emails", "social"],
    createdAt: "5 min ago",
  },
  {
    id: "2",
    title: "Weekly Performance Report",
    description: "Analyze last week's campaign performance",
    agent: "Analytics Agent",
    status: "reviewing",
    progress: 100,
    outputs: ["reports"],
    createdAt: "1 hour ago",
  },
  {
    id: "3",
    title: "Lead Scoring Update",
    description: "Update lead scores based on recent activity",
    agent: "Sales Agent",
    status: "completed",
    progress: 100,
    outputs: ["segments"],
    createdAt: "2 hours ago",
  },
  {
    id: "4",
    title: "Competitor Analysis",
    description: "Research competitor positioning and messaging",
    agent: "Research Agent",
    status: "completed",
    progress: 100,
    outputs: ["reports"],
    createdAt: "Yesterday",
  },
]

const statusConfig = {
  running: { label: "Running", color: "bg-blue-500", icon: "spinner", className: "animate-spin" },
  reviewing: { label: "Needs Review", color: "bg-amber-500", icon: "eye", className: "" },
  completed: { label: "Completed", color: "bg-emerald-500", icon: "check", className: "" },
  failed: { label: "Failed", color: "bg-red-500", icon: "error", className: "" },
}

export default function LiteTasksPage() {
  const [filter, setFilter] = useState<string>("all")
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const filteredTasks = filter === "all" 
    ? tasks 
    : tasks.filter(t => t.status === filter)

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
              { id: "running", label: "Running" },
              { id: "reviewing", label: "Needs Review" },
              { id: "completed", label: "Completed" },
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
          {filteredTasks.map((task, index) => {
            const status = statusConfig[task.status as keyof typeof statusConfig]
            
            return (
              <Link key={task.id} href={`/lite/tasks/${task.id}`}>
                <Card 
                  className={cn(
                    "p-6 border-border/50 hover:border-border transition-all cursor-pointer group",
                    "transition-all duration-500",
                    mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                  )}
                  style={{ transitionDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-start gap-5">
                    {/* Status Icon */}
                    <div className={cn(
                      "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
                      task.status === "running" && "bg-blue-500/10",
                      task.status === "reviewing" && "bg-amber-500/10",
                      task.status === "completed" && "bg-emerald-500/10"
                    )}>
                      <Icon 
                        name={status.icon as any} 
                        size="lg" 
                        className={cn(
                          task.status === "running" && "text-blue-500",
                          task.status === "reviewing" && "text-amber-500",
                          task.status === "completed" && "text-emerald-500",
                          status.className
                        )} 
                      />
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold text-foreground group-hover:text-emerald-500 transition-colors">
                          {task.title}
                        </h3>
                        <Badge 
                          variant="outline" 
                          className={cn(
                            "text-xs",
                            task.status === "running" && "text-blue-500 border-blue-500/30 bg-blue-500/10",
                            task.status === "reviewing" && "text-amber-500 border-amber-500/30 bg-amber-500/10",
                            task.status === "completed" && "text-emerald-500 border-emerald-500/30 bg-emerald-500/10"
                          )}
                        >
                          {status.label}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-3">{task.description}</p>
                      
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Icon name="ai" size="xs" />
                          {task.agent}
                        </span>
                        <span className="flex items-center gap-1">
                          <Icon name="clock" size="xs" />
                          {task.createdAt}
                        </span>
                        {task.outputs.map(output => (
                          <Badge key={output} variant="secondary" className="text-[10px]">
                            {output}
                          </Badge>
                        ))}
                      </div>
                      
                      {/* Progress bar for running tasks */}
                      {task.status === "running" && (
                        <div className="mt-4">
                          <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-500"
                              style={{ width: `${task.progress}%` }}
                            />
                          </div>
                          <div className="flex items-center justify-between mt-1.5 text-xs text-muted-foreground">
                            <span>{task.progress}% complete</span>
                            {task.eta && <span>ETA: {task.eta}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Action */}
                    <div className="shrink-0">
                      {task.status === "reviewing" && (
                        <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white">
                          Review
                        </Button>
                      )}
                      {task.status === "completed" && (
                        <Button size="sm" variant="outline">
                          View
                        </Button>
                      )}
                      {task.status === "running" && (
                        <Icon name="chevronRight" size="md" className="text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
                      )}
                    </div>
                  </div>
                </Card>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
