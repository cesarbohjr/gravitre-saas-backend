"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import Link from "next/link"

// Quick action cards for common tasks
const quickActions = [
  {
    title: "Create Campaign",
    description: "Launch a new marketing campaign",
    icon: "sparkles",
    color: "emerald",
    href: "/lite/assign?type=campaign",
  },
  {
    title: "Draft Emails",
    description: "Generate email sequences",
    icon: "mail",
    color: "blue",
    href: "/lite/assign?type=email",
  },
  {
    title: "Build Segment",
    description: "Create audience segments",
    icon: "users",
    color: "violet",
    href: "/lite/assign?type=segment",
  },
  {
    title: "Analyze Data",
    description: "Get insights from your data",
    icon: "chart",
    color: "amber",
    href: "/lite/assign?type=analysis",
  },
]

// Sample tasks in progress
const activeTasks = [
  {
    id: "1",
    title: "Q3 Healthcare Campaign",
    agent: "Marketing Agent",
    status: "running",
    progress: 65,
    eta: "2 min",
  },
  {
    id: "2",
    title: "Weekly Performance Report",
    agent: "Analytics Agent",
    status: "reviewing",
    progress: 100,
    eta: null,
  },
]

// Recent deliverables
const recentDeliverables = [
  {
    id: "1",
    title: "Email Sequence - Product Launch",
    type: "emails",
    agent: "Marketing Agent",
    confidence: 94,
    time: "10 min ago",
    status: "ready",
  },
  {
    id: "2",
    title: "Enterprise Segment",
    type: "segment",
    agent: "Sales Agent",
    confidence: 88,
    time: "1 hour ago",
    status: "approved",
  },
  {
    id: "3",
    title: "Competitor Analysis Report",
    type: "report",
    agent: "Research Agent",
    confidence: 91,
    time: "2 hours ago",
    status: "ready",
  },
]

// Available agents
const agents = [
  { id: "1", name: "Marketing Agent", department: "Marketing", status: "online", tasks: 3 },
  { id: "2", name: "Sales Agent", department: "Sales", status: "online", tasks: 1 },
  { id: "3", name: "Analytics Agent", department: "Operations", status: "busy", tasks: 5 },
]

const colorMap: Record<string, { bg: string; text: string; border: string }> = {
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-500", border: "border-emerald-500/20" },
  blue: { bg: "bg-blue-500/10", text: "text-blue-500", border: "border-blue-500/20" },
  violet: { bg: "bg-violet-500/10", text: "text-violet-500", border: "border-violet-500/20" },
  amber: { bg: "bg-amber-500/10", text: "text-amber-500", border: "border-amber-500/20" },
}

export default function LiteDashboard() {
  const [taskInput, setTaskInput] = useState("")
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const handleQuickAssign = () => {
    if (taskInput.trim()) {
      // Navigate to assign flow with prefilled task
      window.location.href = `/lite/assign?task=${encodeURIComponent(taskInput)}`
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section with Main Input */}
      <div className="relative overflow-hidden border-b border-border">
        {/* Animated background */}
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-blue-500/5" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDuration: "4s" }} />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDuration: "6s", animationDelay: "2s" }} />
        
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
          {/* Greeting */}
          <div className={cn(
            "text-center mb-6 sm:mb-8 transition-all duration-700",
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          )}>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
              Good morning, John
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground">
              Your AI team is ready. What should they do?
            </p>
          </div>

          {/* Main Input Box */}
          <div className={cn(
            "transition-all duration-700 delay-100",
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          )}>
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 via-blue-500/20 to-violet-500/20 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative bg-card border border-border rounded-xl p-2 shadow-lg">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3">
                  <div className="flex-1 relative">
                    <Input
                      value={taskInput}
                      onChange={(e) => setTaskInput(e.target.value)}
                      placeholder="What should your AI team do?"
                      className="border-0 bg-transparent text-base sm:text-lg h-12 sm:h-14 px-3 sm:px-4 focus-visible:ring-0 placeholder:text-muted-foreground/50"
                      onKeyDown={(e) => e.key === "Enter" && handleQuickAssign()}
                    />
                  </div>
                  <Button 
                    onClick={handleQuickAssign}
                    disabled={!taskInput.trim()}
                    className="h-11 sm:h-11 px-6 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium gap-2 transition-all"
                  >
                    <Icon name="send" size="sm" />
                    <span className="sm:inline">Assign Work</span>
                  </Button>
                </div>
                
                {/* Agent selector chips */}
                <div className="flex flex-wrap items-center gap-2 px-3 sm:px-4 pb-2 pt-1">
                  <span className="text-xs text-muted-foreground">Assign to:</span>
                  {agents.slice(0, 3).map((agent) => (
                    <button
                      key={agent.id}
                      onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)}
                      className={cn(
                        "px-2.5 sm:px-3 py-1 rounded-full text-xs font-medium transition-all",
                        selectedAgent === agent.id
                          ? "bg-emerald-500/20 text-emerald-500 ring-1 ring-emerald-500/30"
                          : "bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {agent.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Example prompts */}
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              {[
                "Create a Q3 campaign for healthcare",
                "Draft follow-up emails for leads",
                "Analyze last month's performance",
              ].map((example) => (
                <button
                  key={example}
                  onClick={() => setTaskInput(example)}
                  className="px-3 py-1.5 rounded-full text-xs text-muted-foreground bg-secondary/50 hover:bg-secondary hover:text-foreground transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Quick Actions */}
        <div className={cn(
          "mb-8 sm:mb-12 transition-all duration-700 delay-200",
          mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
        )}>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 sm:mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            {quickActions.map((action) => {
              const colors = colorMap[action.color]
              return (
                <Link key={action.title} href={action.href}>
                  <Card className="group relative p-4 sm:p-5 hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden border-border/50 hover:border-border min-h-[120px] sm:min-h-0">
                    <div className={cn(
                      "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300",
                      colors.bg
                    )} />
                    <div className="relative">
                      <div className={cn(
                        "w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center mb-2 sm:mb-3 transition-transform group-hover:scale-110",
                        colors.bg
                      )}>
                        <Icon name={action.icon as any} size="md" className={colors.text} />
                      </div>
                      <h3 className="font-semibold text-foreground text-sm sm:text-base mb-1">{action.title}</h3>
                      <p className="text-[11px] sm:text-xs text-muted-foreground line-clamp-2">{action.description}</p>
                    </div>
                  </Card>
                </Link>
              )
            })}
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid lg:grid-cols-2 gap-6 sm:gap-8">
          {/* Active Tasks */}
          <div className={cn(
            "transition-all duration-700 delay-300",
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          )}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                In Progress
              </h2>
              <Link href="/lite/tasks" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                View all
              </Link>
            </div>
            <div className="space-y-3">
              {activeTasks.map((task) => (
                <Card key={task.id} className="p-4 border-border/50">
                  <div className="flex items-start gap-4">
                    {/* Status indicator */}
                    <div className={cn(
                      "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
                      task.status === "running" ? "bg-blue-500/10" : "bg-amber-500/10"
                    )}>
                      {task.status === "running" ? (
                        <Icon name="spinner" size="md" className="text-blue-500 animate-spin" />
                      ) : (
                        <Icon name="eye" size="md" className="text-amber-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-foreground truncate">{task.title}</h3>
                        {task.status === "reviewing" && (
                          <Badge variant="outline" className="text-amber-500 border-amber-500/30 bg-amber-500/10">
                            Needs Review
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mb-2">{task.agent}</p>
                      
                      {/* Progress bar */}
                      <div className="relative">
                        <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                          <div 
                            className={cn(
                              "h-full rounded-full transition-all duration-500",
                              task.status === "running" 
                                ? "bg-gradient-to-r from-blue-500 to-blue-400" 
                                : "bg-gradient-to-r from-amber-500 to-amber-400"
                            )}
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                        <div className="flex items-center justify-between mt-1.5">
                          <span className="text-[10px] text-muted-foreground">{task.progress}% complete</span>
                          {task.eta && (
                            <span className="text-[10px] text-muted-foreground">ETA: {task.eta}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}

              {activeTasks.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  <Icon name="check" size="xl" className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No tasks in progress</p>
                </div>
              )}
            </div>
          </div>

          {/* Recent Deliverables */}
          <div className={cn(
            "transition-all duration-700 delay-400",
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          )}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Recent Deliverables
              </h2>
              <Link href="/lite/deliverables" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                View all
              </Link>
            </div>
            <div className="space-y-3">
              {recentDeliverables.map((item) => (
                <Card key={item.id} className="p-4 border-border/50 group hover:border-border transition-colors cursor-pointer">
                  <div className="flex items-start gap-4">
                    {/* Type indicator */}
                    <div className={cn(
                      "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
                      item.status === "ready" ? "bg-emerald-500/10" : "bg-secondary"
                    )}>
                      <Icon 
                        name={item.type === "emails" ? "mail" : item.type === "segment" ? "users" : "file"} 
                        size="md" 
                        className={item.status === "ready" ? "text-emerald-500" : "text-muted-foreground"} 
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-foreground truncate group-hover:text-emerald-500 transition-colors">
                          {item.title}
                        </h3>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{item.agent}</span>
                        <span className="text-muted-foreground/30">|</span>
                        <span>{item.time}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Confidence */}
                      <div className="text-right">
                        <div className="text-sm font-semibold text-foreground">{item.confidence}%</div>
                        <div className="text-[10px] text-muted-foreground">confidence</div>
                      </div>
                      {item.status === "ready" && (
                        <Button size="sm" className="h-8 bg-emerald-500 hover:bg-emerald-600 text-white">
                          Review
                        </Button>
                      )}
                      {item.status === "approved" && (
                        <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">
                          <Icon name="check" size="xs" className="mr-1" />
                          Approved
                        </Badge>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </div>

        {/* Your AI Team */}
        <div className={cn(
          "mt-12 transition-all duration-700 delay-500",
          mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
        )}>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Your AI Team
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <Card key={agent.id} className="p-5 border-border/50 hover:border-border transition-colors">
                <div className="flex items-center gap-4">
                  {/* Avatar */}
                  <div className="relative">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-500/20 to-blue-500/20 flex items-center justify-center">
                      <Icon name="ai" size="lg" className="text-foreground" />
                    </div>
                    <div className={cn(
                      "absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full ring-2 ring-background",
                      agent.status === "online" ? "bg-emerald-500" : "bg-amber-500"
                    )} />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground">{agent.name}</h3>
                    <p className="text-xs text-muted-foreground">{agent.department}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-foreground">{agent.tasks}</div>
                    <div className="text-[10px] text-muted-foreground">tasks</div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
