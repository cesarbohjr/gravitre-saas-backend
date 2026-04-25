"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import {
  MorphingBackground,
  GlowOrb,
  ParticleField,
  StatusBeacon,
  AnimatedCounter,
  ActivityIndicator,
  TypingIndicator
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  CheckSquare,
  Plus,
  Search,
  Clock,
  CheckCircle2,
  AlertCircle,
  Play,
  Pause,
  MoreHorizontal,
  Calendar,
  User,
  Zap,
  Filter,
  ArrowUpRight,
  Activity,
  TrendingUp,
  Bot,
  Sparkles,
} from "lucide-react"

interface Task {
  id: string
  title: string
  description: string
  status: "pending" | "in_progress" | "completed" | "failed"
  priority: "low" | "medium" | "high" | "critical"
  assignedAgent: string
  dueDate?: string
  createdAt: string
  completedAt?: string
  progress?: number
}

const tasks: Task[] = [
  {
    id: "1",
    title: "Sync customer data from Salesforce",
    description: "Pull latest customer records and update CRM",
    status: "in_progress",
    priority: "high",
    assignedAgent: "Nexus",
    createdAt: "2 hours ago",
    progress: 65,
  },
  {
    id: "2",
    title: "Generate weekly marketing report",
    description: "Compile campaign metrics and insights",
    status: "completed",
    priority: "medium",
    assignedAgent: "Atlas",
    createdAt: "1 day ago",
    completedAt: "3 hours ago",
  },
  {
    id: "3",
    title: "Process invoice batch #4521",
    description: "OCR and validate incoming invoices",
    status: "pending",
    priority: "medium",
    assignedAgent: "Oracle",
    createdAt: "30 minutes ago",
    dueDate: "Today, 5:00 PM",
  },
  {
    id: "4",
    title: "Data quality check - Q4 records",
    description: "Validate and deduplicate database records",
    status: "completed",
    priority: "low",
    assignedAgent: "Sentinel",
    createdAt: "2 days ago",
    completedAt: "1 day ago",
  },
  {
    id: "5",
    title: "Route support tickets",
    description: "Categorize and assign incoming tickets",
    status: "failed",
    priority: "critical",
    assignedAgent: "Harbor",
    createdAt: "1 hour ago",
  },
  {
    id: "6",
    title: "Update lead scoring model",
    description: "Retrain model with latest conversion data",
    status: "pending",
    priority: "high",
    assignedAgent: "Nexus",
    dueDate: "Tomorrow, 9:00 AM",
    createdAt: "4 hours ago",
  },
]

const statusConfig = {
  pending: { label: "Pending", color: "text-zinc-400", bg: "bg-zinc-500/10", icon: Clock },
  in_progress: { label: "In Progress", color: "text-blue-400", bg: "bg-blue-500/10", icon: Play },
  completed: { label: "Completed", color: "text-emerald-400", bg: "bg-emerald-500/10", icon: CheckCircle2 },
  failed: { label: "Failed", color: "text-red-400", bg: "bg-red-500/10", icon: AlertCircle },
}

const priorityConfig = {
  low: { label: "Low", color: "text-zinc-400", dot: "bg-zinc-400" },
  medium: { label: "Medium", color: "text-amber-400", dot: "bg-amber-400" },
  high: { label: "High", color: "text-orange-400", dot: "bg-orange-400" },
  critical: { label: "Critical", color: "text-red-400", dot: "bg-red-400" },
}

function TaskCard({ task, isSelected, onClick, index }: { task: Task; isSelected: boolean; onClick: () => void; index: number }) {
  const status = statusConfig[task.status]
  const priority = priorityConfig[task.priority]
  const StatusIcon = status.icon

  return (
    <motion.button
      onClick={onClick}
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, type: "spring", stiffness: 100 }}
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={cn(
        "w-full text-left p-4 rounded-xl border transition-all relative overflow-hidden",
        isSelected
          ? "border-blue-500/50 bg-gradient-to-br from-blue-500/10 to-cyan-500/5 ring-2 ring-blue-500/20 shadow-lg shadow-blue-500/10"
          : "border-border bg-card/50 backdrop-blur-sm hover:border-border/80 hover:bg-card/80 hover:shadow-md"
      )}
    >
      {/* Glow effect for selected */}
      {isSelected && (
        <div className="absolute -inset-px bg-gradient-to-r from-blue-500/20 via-transparent to-cyan-500/20 rounded-xl pointer-events-none" />
      )}
      
      {/* Processing indicator */}
      {task.status === "in_progress" && (
        <motion.div 
          className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500"
          animate={{ backgroundPosition: ["0% 0%", "100% 0%", "0% 0%"] }}
          transition={{ duration: 2, repeat: Infinity }}
          style={{ backgroundSize: "200% 100%" }}
        />
      )}
      
      <div className="relative flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <StatusBeacon 
              status={task.status === "failed" ? "error" : task.status === "in_progress" ? "processing" : task.status === "completed" ? "active" : "idle"} 
              size="sm" 
              pulse={task.status === "in_progress"}
            />
            <span className={cn("text-[10px] font-semibold uppercase tracking-wider", priority.color)}>
              {priority.label}
            </span>
          </div>
          <h3 className="font-semibold text-foreground text-sm truncate">{task.title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{task.description}</p>
        </div>
        <motion.div 
          className={cn("shrink-0 p-2.5 rounded-xl", status.bg)}
          animate={task.status === "in_progress" ? { scale: [1, 1.1, 1] } : {}}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <StatusIcon className={cn("h-4 w-4", status.color)} />
        </motion.div>
      </div>

      <div className="relative flex items-center justify-between mt-3 pt-3 border-t border-border/30">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-secondary/50">
            <Bot className="h-3 w-3" />
            {task.assignedAgent}
          </span>
          {task.dueDate && (
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {task.dueDate}
            </span>
          )}
        </div>
        {task.progress !== undefined && (
          <div className="flex items-center gap-2">
            <div className="w-20 h-1.5 rounded-full bg-secondary/50 overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${task.progress}%` }}
                transition={{ duration: 0.8, delay: index * 0.05 }}
              />
            </div>
            <span className="text-[10px] font-medium text-blue-400">{task.progress}%</span>
          </div>
        )}
      </div>
    </motion.button>
  )
}

export default function TasksPage() {
  const [selectedTask, setSelectedTask] = useState<string>("1")
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")

  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === "all" || task.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const selected = tasks.find((t) => t.id === selectedTask)

  const pendingCount = tasks.filter((t) => t.status === "pending").length
  const inProgressCount = tasks.filter((t) => t.status === "in_progress").length
  const completedCount = tasks.filter((t) => t.status === "completed").length

  return (
    <AppShell title="Tasks">
      <div className="relative flex flex-col lg:flex-row h-full overflow-hidden">
        {/* Premium ambient background */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["amber", "emerald", "blue"]} />
          <div className="absolute inset-0 bg-background/90 backdrop-blur-3xl" />
        </div>
        
        {/* Ambient orbs */}
        <div className="absolute top-20 right-20 pointer-events-none z-0">
          <GlowOrb size={200} color="amber" intensity={0.2} />
        </div>
        <div className="absolute bottom-40 left-1/3 pointer-events-none z-0">
          <GlowOrb size={150} color="emerald" intensity={0.15} />
        </div>

        {/* Left Panel - Task List */}
        <div className="relative z-10 flex-1 flex flex-col lg:border-r border-border/50 lg:max-w-md backdrop-blur-sm">
          <PageHeader
            title="Tasks"
            description="Monitor and manage agent tasks"
            icon={CheckSquare}
            iconColor="from-blue-500/20 to-cyan-500/20"
            actions={
              <Button size="sm" className="gap-2">
                <Plus className="h-4 w-4" />
                New Task
              </Button>
            }
          >
            <StatsGrid columns={3}>
              <StatCard label="Pending" value={pendingCount} />
              <StatCard label="In Progress" value={inProgressCount} variant="info" />
              <StatCard label="Completed" value={completedCount} variant="success" />
            </StatsGrid>
          </PageHeader>

          {/* Search & Filter */}
          <div className="p-4 border-b border-border">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search tasks..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-9 rounded-lg border border-border bg-secondary pl-9 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <Button variant="outline" size="sm" className="gap-2">
                <Filter className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Filter</span>
              </Button>
            </div>
            
            {/* Status Filter Pills */}
            <div className="flex gap-1.5 mt-3 overflow-x-auto pb-1">
              {["all", "pending", "in_progress", "completed", "failed"].map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={cn(
                    "px-3 py-1 rounded-full text-xs font-medium transition-colors whitespace-nowrap",
                    statusFilter === status
                      ? "bg-info/20 text-info"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {status === "all" ? "All" : status === "in_progress" ? "In Progress" : status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Task List */}
          <div className="relative flex-1 overflow-y-auto p-4 space-y-3 scrollbar-on-hover">
            {/* Particles when tasks are running */}
            {inProgressCount > 0 && (
              <ParticleField count={20} color="blue" interactive={false} className="opacity-30" />
            )}
            
            <AnimatePresence mode="popLayout">
              {filteredTasks.map((task, index) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  index={index}
                  isSelected={selectedTask === task.id}
                  onClick={() => setSelectedTask(task.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        </div>

        {/* Right Panel - Task Detail */}
        <div className="relative z-10 flex-1 flex flex-col overflow-hidden bg-card/30 backdrop-blur-sm">
          {/* Top gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-emerald-500 to-blue-500" />
          
          {selected ? (
            <motion.div
              key={selected.id}
              initial={{ opacity: 0, x: 30, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 100 }}
              className="flex-1 flex flex-col"
            >
              {/* Detail Header */}
              <div className="p-6 border-b border-border">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider",
                        statusConfig[selected.status].bg,
                        statusConfig[selected.status].color
                      )}>
                        {statusConfig[selected.status].label}
                      </span>
                      <span className={cn(
                        "flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider",
                        priorityConfig[selected.priority].color
                      )}>
                        <div className={cn("h-1.5 w-1.5 rounded-full", priorityConfig[selected.priority].dot)} />
                        {priorityConfig[selected.priority].label} Priority
                      </span>
                    </div>
                    <h2 className="text-xl font-semibold text-foreground">{selected.title}</h2>
                    <p className="text-sm text-muted-foreground mt-1">{selected.description}</p>
                  </div>
                  <Button variant="ghost" size="icon">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </div>

                {/* Progress */}
                {selected.progress !== undefined && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-muted-foreground">Progress</span>
                      <span className="text-sm font-medium text-foreground">{selected.progress}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-secondary overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${selected.progress}%` }}
                        transition={{ duration: 0.5 }}
                        className="h-full bg-info rounded-full"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Detail Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Assigned Agent */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Assigned Agent
                  </h3>
                  <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card">
                    <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                      <Zap className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{selected.assignedAgent}</p>
                      <p className="text-xs text-muted-foreground">AI Agent</p>
                    </div>
                    <Button variant="ghost" size="sm" className="ml-auto gap-1.5">
                      View Agent
                      <ArrowUpRight className="h-3 w-3" />
                    </Button>
                  </div>
                </div>

                {/* Timeline */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Timeline
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 text-sm">
                      <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-foreground">Created</p>
                        <p className="text-xs text-muted-foreground">{selected.createdAt}</p>
                      </div>
                    </div>
                    {selected.completedAt && (
                      <div className="flex items-center gap-3 text-sm">
                        <div className="h-8 w-8 rounded-full bg-emerald-500/10 flex items-center justify-center">
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        </div>
                        <div>
                          <p className="text-foreground">Completed</p>
                          <p className="text-xs text-muted-foreground">{selected.completedAt}</p>
                        </div>
                      </div>
                    )}
                    {selected.dueDate && !selected.completedAt && (
                      <div className="flex items-center gap-3 text-sm">
                        <div className="h-8 w-8 rounded-full bg-amber-500/10 flex items-center justify-center">
                          <Calendar className="h-4 w-4 text-amber-400" />
                        </div>
                        <div>
                          <p className="text-foreground">Due</p>
                          <p className="text-xs text-muted-foreground">{selected.dueDate}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions Footer */}
              <div className="p-4 border-t border-border bg-secondary/30">
                <div className="flex gap-2">
                  {selected.status === "pending" && (
                    <Button className="flex-1 gap-2">
                      <Play className="h-4 w-4" />
                      Start Task
                    </Button>
                  )}
                  {selected.status === "in_progress" && (
                    <>
                      <Button variant="outline" className="flex-1 gap-2">
                        <Pause className="h-4 w-4" />
                        Pause
                      </Button>
                      <Button className="flex-1 gap-2">
                        <CheckCircle2 className="h-4 w-4" />
                        Mark Complete
                      </Button>
                    </>
                  )}
                  {selected.status === "failed" && (
                    <Button className="flex-1 gap-2">
                      <Play className="h-4 w-4" />
                      Retry Task
                    </Button>
                  )}
                  {selected.status === "completed" && (
                    <Button variant="outline" className="flex-1 gap-2">
                      <ArrowUpRight className="h-4 w-4" />
                      View Output
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              Select a task to view details
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
