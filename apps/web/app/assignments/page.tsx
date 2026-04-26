"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { 
  Megaphone, 
  TrendingUp, 
  Database, 
  PieChart, 
  Headphones,
  type LucideIcon 
} from "lucide-react"

// Types
interface Assignment {
  id: string
  title: string
  brief: string
  agent: { name: string; role: string; gradient: string; icon: LucideIcon }
  status: "running" | "completed" | "pending" | "failed" | "needs_approval"
  progress: number
  steps: { name: string; status: "done" | "running" | "pending" }[]
  createdAt: string
  completedAt?: string
  outputTypes: string[]
  destination: string
  confidence?: number
}

// Agent icon mapping based on role
const agentIcons: Record<string, LucideIcon> = {
  "Marketing Agent": Megaphone,
  "Marketing Operator": Megaphone,
  "Sales Assistant": TrendingUp,
  "Data Quality Agent": Database,
  "Finance Reporter": PieChart,
  "Support Coordinator": Headphones,
}

// Mock Data
const assignments: Assignment[] = [
  {
    id: "assign-001",
    title: "Q3 Healthcare Campaign",
    brief: "Create multi-channel campaign targeting healthcare decision makers",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "running",
    progress: 67,
    steps: [
      { name: "Research", status: "done" },
      { name: "Strategy", status: "done" },
      { name: "Content", status: "running" },
      { name: "Review", status: "pending" },
    ],
    createdAt: "2 hours ago",
    outputTypes: ["Emails", "Social Posts", "Segments"],
    destination: "HubSpot + Outlook",
  },
  {
    id: "assign-002",
    title: "Weekly Performance Report",
    brief: "Generate comprehensive weekly marketing performance analysis",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "needs_approval",
    progress: 100,
    steps: [
      { name: "Data Pull", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "done" },
      { name: "Approval", status: "running" },
    ],
    createdAt: "5 hours ago",
    completedAt: "4 hours ago",
    outputTypes: ["Report"],
    destination: "Slack",
    confidence: 94,
  },
  {
    id: "assign-003",
    title: "Lead Scoring Analysis",
    brief: "Analyze and score all leads from Q2 campaign activities",
    agent: { name: "Nexus", role: "Sales Assistant", gradient: "from-blue-500 to-indigo-500", icon: TrendingUp },
    status: "completed",
    progress: 100,
    steps: [
      { name: "Import", status: "done" },
      { name: "Score", status: "done" },
      { name: "Segment", status: "done" },
      { name: "Export", status: "done" },
    ],
    createdAt: "1 day ago",
    completedAt: "1 day ago",
    outputTypes: ["Report", "Segments"],
    destination: "Salesforce",
    confidence: 98,
  },
  {
    id: "assign-004",
    title: "Email Sequence - Re-engagement",
    brief: "Design 5-email re-engagement sequence for dormant leads",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "pending",
    progress: 0,
    steps: [
      { name: "Research", status: "pending" },
      { name: "Draft", status: "pending" },
      { name: "Review", status: "pending" },
      { name: "Publish", status: "pending" },
    ],
    createdAt: "Just now",
    outputTypes: ["Emails"],
    destination: "HubSpot",
  },
  {
    id: "assign-005",
    title: "Competitor Analysis Report",
    brief: "Deep dive analysis of top 5 competitors market positioning",
    agent: { name: "Oracle", role: "Finance Reporter", gradient: "from-violet-500 to-purple-500", icon: PieChart },
    status: "failed",
    progress: 45,
    steps: [
      { name: "Research", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "pending" },
      { name: "Export", status: "pending" },
    ],
    createdAt: "2 days ago",
    outputTypes: ["Report"],
    destination: "Export",
  },
]

const statusConfig: Record<string, { label: string; color: string; bgColor: string; dotColor: string; icon: string }> = {
  running: { label: "Running", color: "text-blue-400", bgColor: "bg-blue-500/10", dotColor: "bg-blue-500", icon: "activity" },
  completed: { label: "Completed", color: "text-emerald-400", bgColor: "bg-emerald-500/10", dotColor: "bg-emerald-500", icon: "check" },
  pending: { label: "Queued", color: "text-amber-400", bgColor: "bg-amber-500/10", dotColor: "bg-amber-500", icon: "clock" },
  failed: { label: "Failed", color: "text-red-400", bgColor: "bg-red-500/10", dotColor: "bg-red-500", icon: "warning" },
  needs_approval: { label: "Needs Approval", color: "text-violet-400", bgColor: "bg-violet-500/10", dotColor: "bg-violet-500", icon: "shield" },
}

// Live Activity Pulse
function ActivityPulse() {
  return (
    <div className="relative flex items-center gap-2">
      <div className="relative h-3 w-3">
        <div className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-75" />
        <div className="relative h-full w-full rounded-full bg-emerald-500" />
      </div>
      <span className="text-xs font-medium text-emerald-400">Live</span>
    </div>
  )
}

// Assignment Card with Rich Detail
function AssignmentCard({ assignment, onClick }: { assignment: Assignment; onClick: () => void }) {
  const status = statusConfig[assignment.status]
  const completedSteps = assignment.steps.filter(s => s.status === "done").length
  const currentStep = assignment.steps.find(s => s.status === "running")

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -4 }}
      onClick={onClick}
      className="group relative overflow-hidden rounded-xl sm:rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-4 sm:p-5 cursor-pointer transition-all hover:border-muted-foreground/30 hover:shadow-lg hover:shadow-black/5"
    >
      {/* Status indicator line */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl",
        assignment.status === "running" && "bg-gradient-to-r from-blue-500 via-blue-400 to-blue-500 animate-pulse",
        assignment.status === "completed" && "bg-emerald-500",
        assignment.status === "pending" && "bg-amber-500",
        assignment.status === "failed" && "bg-red-500",
        assignment.status === "needs_approval" && "bg-gradient-to-r from-violet-500 to-purple-500",
      )} />

      <div className="flex items-start gap-3 sm:gap-4">
        {/* Agent Avatar */}
        <div className="relative shrink-0">
          <div className={cn(
            "h-10 w-10 sm:h-12 sm:w-12 rounded-lg sm:rounded-xl bg-gradient-to-br flex items-center justify-center text-white",
            assignment.agent.gradient
          )}>
            <assignment.agent.icon className="h-5 w-5 sm:h-6 sm:w-6" />
          </div>
          {assignment.status === "running" && (
            <motion.div
              className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-blue-500 flex items-center justify-center"
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              <Icon name="activity" size="xs" className="text-white" />
            </motion.div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4 mb-2">
            <div>
              <h3 className="font-semibold text-foreground group-hover:text-foreground/90 transition-colors line-clamp-1">
                {assignment.title}
              </h3>
              <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                {assignment.brief}
              </p>
            </div>
            <div className={cn(
              "shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
              status.bgColor, status.color
            )}>
              <div className={cn("h-1.5 w-1.5 rounded-full", status.dotColor, assignment.status === "running" && "animate-pulse")} />
              {status.label}
            </div>
          </div>

          {/* Progress Steps */}
          <div className="flex items-center gap-1 mb-3">
            {assignment.steps.map((step, i) => (
              <div key={i} className="flex-1 flex items-center gap-1">
                <div className={cn(
                  "h-1.5 flex-1 rounded-full transition-all",
                  step.status === "done" && "bg-emerald-500",
                  step.status === "running" && "bg-blue-500 animate-pulse",
                  step.status === "pending" && "bg-muted",
                )} />
              </div>
            ))}
          </div>

          {/* Meta Row */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-[11px] sm:text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Icon name="user" size="xs" />
              <span>{assignment.agent.name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Icon name="clock" size="xs" />
              <span>{assignment.createdAt}</span>
            </div>
            {currentStep && (
              <div className="hidden sm:flex items-center gap-1.5 text-blue-400">
                <Icon name="activity" size="xs" />
                <span>{currentStep.name}</span>
              </div>
            )}
            {assignment.confidence && assignment.status !== "running" && (
              <div className="flex items-center gap-1.5 ml-auto">
                <span className={cn(
                  "font-medium",
                  assignment.confidence >= 90 ? "text-emerald-400" : 
                  assignment.confidence >= 70 ? "text-amber-400" : "text-red-400"
                )}>
                  {assignment.confidence}% confident
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Hover reveal: Quick Actions */}
      <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
          <Icon name="eye" size="sm" />
        </Button>
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
          <Icon name="more" size="sm" />
        </Button>
      </div>
    </motion.div>
  )
}

// Stats Card
function StatCard({ stat, index }: { stat: { label: string; value: number; icon: string; color: string; trend?: string }; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className={cn(
        "relative overflow-hidden rounded-2xl border p-5 transition-all",
        "border-border bg-card/50 hover:bg-secondary/30"
      )}
    >
      <div className="absolute -top-6 -right-6 h-24 w-24 rounded-full opacity-10" style={{
        background: stat.color === "blue" ? "radial-gradient(circle, #3b82f6 0%, transparent 70%)" :
                   stat.color === "emerald" ? "radial-gradient(circle, #10b981 0%, transparent 70%)" :
                   stat.color === "amber" ? "radial-gradient(circle, #f59e0b 0%, transparent 70%)" :
                   "radial-gradient(circle, #ef4444 0%, transparent 70%)"
      }} />
      
      <div className="relative flex items-start justify-between">
        <div>
          <div className={cn(
            "h-8 w-8 sm:h-10 sm:w-10 rounded-lg sm:rounded-xl flex items-center justify-center mb-2 sm:mb-3",
            stat.color === "blue" && "bg-blue-500/10",
            stat.color === "emerald" && "bg-emerald-500/10",
            stat.color === "amber" && "bg-amber-500/10",
            stat.color === "red" && "bg-red-500/10",
            stat.color === "violet" && "bg-violet-500/10",
          )}>
            <Icon 
              name={stat.icon as any} 
              size="sm" 
              className={cn(
                stat.color === "blue" && "text-blue-400",
                stat.color === "emerald" && "text-emerald-400",
                stat.color === "amber" && "text-amber-400",
                stat.color === "red" && "text-red-400",
                stat.color === "violet" && "text-violet-400",
              )} 
            />
          </div>
          <p className="text-2xl sm:text-3xl font-bold text-foreground">{stat.value}</p>
          <p className="text-xs sm:text-sm text-muted-foreground">{stat.label}</p>
        </div>
        {stat.trend && (
          <span className={cn(
            "text-[10px] sm:text-xs font-medium",
            stat.trend.startsWith("+") ? "text-emerald-400" : "text-red-400"
          )}>
            {stat.trend}
          </span>
        )}
      </div>
    </motion.div>
  )
}

export default function AssignmentsPage() {
  const router = useRouter()
  const [filter, setFilter] = useState<string>("all")
  const [viewMode, setViewMode] = useState<"list" | "kanban">("list")
  
  const filteredAssignments = filter === "all" 
    ? assignments 
    : assignments.filter(a => a.status === filter)

  const stats = [
    { label: "In Progress", value: assignments.filter(a => a.status === "running").length, icon: "activity", color: "blue", trend: "+2 today" },
    { label: "Completed", value: assignments.filter(a => a.status === "completed").length, icon: "check", color: "emerald", trend: "+5 this week" },
    { label: "Pending Approval", value: assignments.filter(a => a.status === "needs_approval").length, icon: "shield", color: "violet" },
    { label: "Queued", value: assignments.filter(a => a.status === "pending").length, icon: "clock", color: "amber" },
  ]

  const filterOptions = [
    { id: "all", label: "All", count: assignments.length },
    { id: "running", label: "Running", count: assignments.filter(a => a.status === "running").length },
    { id: "needs_approval", label: "Needs Approval", count: assignments.filter(a => a.status === "needs_approval").length },
    { id: "completed", label: "Completed", count: assignments.filter(a => a.status === "completed").length },
    { id: "pending", label: "Queued", count: assignments.filter(a => a.status === "pending").length },
    { id: "failed", label: "Failed", count: assignments.filter(a => a.status === "failed").length },
  ]

  return (
    <AppShell title="Assignments">
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="relative overflow-hidden border-b border-border">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-blue-500/5" />
          <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
          
          <div className="relative px-4 sm:px-8 py-4 sm:py-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 sm:mb-6">
              <div className="flex items-center gap-3 sm:gap-4">
                <motion.div 
                  className="h-10 w-10 sm:h-14 sm:w-14 rounded-xl sm:rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center ring-1 ring-emerald-500/20"
                  animate={{ 
                    boxShadow: ["0 0 20px rgba(16, 185, 129, 0.1)", "0 0 40px rgba(16, 185, 129, 0.2)", "0 0 20px rgba(16, 185, 129, 0.1)"]
                  }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Icon name="tasks" size="lg" className="text-emerald-400" />
                </motion.div>
                <div>
                  <div className="flex items-center gap-2 sm:gap-3">
                    <h1 className="text-lg sm:text-2xl font-bold text-foreground">Work Assignments</h1>
                    <ActivityPulse />
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground hidden sm:block">Monitor and manage tasks assigned to your AI team</p>
                </div>
              </div>
              
              <Button 
                className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0 shadow-lg shadow-emerald-500/25 w-full sm:w-auto"
                onClick={() => router.push("/assignments/new")}
              >
                <Icon name="add" size="sm" />
                New Assignment
              </Button>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              {stats.map((stat, i) => (
                <StatCard key={stat.label} stat={stat} index={i} />
              ))}
            </div>
          </div>
        </div>

        {/* Filters & Content */}
        <div className="flex-1 px-4 sm:px-8 py-4 sm:py-6">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-0 mb-4 sm:mb-6">
            <div className="flex items-center gap-1.5 sm:gap-2 p-1 rounded-xl bg-secondary/50 overflow-x-auto">
              {filterOptions.slice(0, 4).map((option) => (
                <button
                  key={option.id}
                  onClick={() => setFilter(option.id)}
                  className={cn(
                    "flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-medium transition-all whitespace-nowrap",
                    filter === option.id
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {option.label}
                  <span className={cn(
                    "px-1 sm:px-1.5 py-0.5 rounded-md text-[10px] sm:text-xs",
                    filter === option.id ? "bg-secondary" : "bg-transparent"
                  )}>
                    {option.count}
                  </span>
                </button>
              ))}
              {/* Show remaining filters in dropdown on mobile */}
              <div className="hidden sm:contents">
                {filterOptions.slice(4).map((option) => (
                  <button
                    key={option.id}
                    onClick={() => setFilter(option.id)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
                      filter === option.id
                        ? "bg-card text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {option.label}
                    <span className={cn(
                      "px-1.5 py-0.5 rounded-md text-xs",
                      filter === option.id ? "bg-secondary" : "bg-transparent"
                    )}>
                      {option.count}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2 h-9">
                <Icon name="filter" size="sm" />
                <span className="hidden sm:inline">Filter</span>
              </Button>
              <div className="flex items-center p-1 rounded-lg bg-secondary/50">
                <button
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "p-2 rounded-md transition-all",
                    viewMode === "list" ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon name="rows" size="sm" />
                </button>
                <button
                  onClick={() => setViewMode("kanban")}
                  className={cn(
                    "p-2 rounded-md transition-all",
                    viewMode === "kanban" ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon name="grid" size="sm" />
                </button>
              </div>
            </div>
          </div>

          {/* Assignment List */}
          <AnimatePresence mode="popLayout">
            <motion.div layout className="grid grid-cols-1 gap-4">
              {filteredAssignments.map((assignment) => (
                <AssignmentCard
                  key={assignment.id}
                  assignment={assignment}
                  onClick={() => router.push(`/assignments/${assignment.id}`)}
                />
              ))}
            </motion.div>
          </AnimatePresence>

          {filteredAssignments.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-20"
            >
              <div className="h-20 w-20 rounded-2xl bg-secondary flex items-center justify-center mb-4">
                <Icon name="tasks" size="xl" className="text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">No assignments found</h3>
              <p className="text-sm text-muted-foreground mb-4">Try adjusting your filters or create a new assignment</p>
              <Button onClick={() => router.push("/assignments/new")} className="gap-2">
                <Icon name="add" size="sm" />
                New Assignment
              </Button>
            </motion.div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
