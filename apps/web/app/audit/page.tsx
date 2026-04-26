"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import {
  Search,
  ChevronDown,
  AlertCircle,
  RefreshCw,
  Calendar,
  CheckCircle2,
  XCircle,
  Shield,
  User,
  Workflow,
  Settings,
  Bot,
  LogIn,
  AlertTriangle,
  Eye,
  Clock,
  Filter
} from "lucide-react"

type Severity = "info" | "warning" | "error"
type ActorType = "user" | "system" | "ai"

interface AuditEvent {
  id: string
  timestamp: string
  timestampFull: string
  action: string
  actionLabel: string
  actor: string
  actorType: ActorType
  resource: string
  resourceType: string
  environment: "production" | "staging"
  severity: Severity
  details: {
    description: string
    metadata: Record<string, string>
  }
}

const fetcher = (url: string) => fetch(url).then((res) => res.json())

const fallbackEvents: AuditEvent[] = [
  {
    id: "evt-001",
    timestamp: "2m ago",
    timestampFull: "2024-01-15 14:32:45 UTC",
    action: "approval.granted",
    actionLabel: "Approval Granted",
    actor: "sarah.chen@company.com",
    actorType: "user",
    resource: "sync-customers",
    resourceType: "workflow",
    environment: "production",
    severity: "info",
    details: {
      description: "Approved retry action for sync-customers workflow run",
      metadata: { run_id: "run-1234", step: "3", approval_type: "manual" },
    },
  },
  {
    id: "evt-002",
    timestamp: "2m ago",
    timestampFull: "2024-01-15 14:32:41 UTC",
    action: "ai.action",
    actionLabel: "AI Action Executed",
    actor: "AI Operator",
    actorType: "ai",
    resource: "sync-customers",
    resourceType: "workflow",
    environment: "production",
    severity: "info",
    details: {
      description: "AI operator executed approved retry on failed run",
      metadata: { action_type: "retry", confidence: "0.94", tokens: "1,245" },
    },
  },
  {
    id: "evt-003",
    timestamp: "15m ago",
    timestampFull: "2024-01-15 14:19:22 UTC",
    action: "workflow.run",
    actionLabel: "Workflow Started",
    actor: "james.wilson@company.com",
    actorType: "user",
    resource: "etl-main-pipeline",
    resourceType: "workflow",
    environment: "production",
    severity: "info",
    details: {
      description: "Manual trigger of etl-main-pipeline workflow",
      metadata: { trigger: "manual", estimated_duration: "12m" },
    },
  },
  {
    id: "evt-004",
    timestamp: "32m ago",
    timestampFull: "2024-01-15 14:02:11 UTC",
    action: "approval.denied",
    actionLabel: "Approval Denied",
    actor: "admin@company.com",
    actorType: "user",
    resource: "postgres-replica",
    resourceType: "connector",
    environment: "staging",
    severity: "warning",
    details: {
      description: "Denied schema migration on postgres-replica connector",
      metadata: { reason: "Incomplete testing", requested_by: "devops@company.com" },
    },
  },
  {
    id: "evt-005",
    timestamp: "1h ago",
    timestampFull: "2024-01-15 13:34:55 UTC",
    action: "connector.update",
    actionLabel: "Connector Updated",
    actor: "devops@company.com",
    actorType: "user",
    resource: "salesforce-api",
    resourceType: "connector",
    environment: "production",
    severity: "info",
    details: {
      description: "Updated connection credentials for salesforce-api",
      metadata: { field: "credentials", masked: "true" },
    },
  },
  {
    id: "evt-006",
    timestamp: "2h ago",
    timestampFull: "2024-01-15 12:28:33 UTC",
    action: "workflow.update",
    actionLabel: "Workflow Modified",
    actor: "sarah.chen@company.com",
    actorType: "user",
    resource: "data-validation",
    resourceType: "workflow",
    environment: "staging",
    severity: "info",
    details: {
      description: "Updated schedule for data-validation workflow",
      metadata: { previous_schedule: "0 */4 * * *", new_schedule: "0 */2 * * *" },
    },
  },
  {
    id: "evt-007",
    timestamp: "3h ago",
    timestampFull: "2024-01-15 11:45:12 UTC",
    action: "user.login",
    actionLabel: "User Login",
    actor: "james.wilson@company.com",
    actorType: "user",
    resource: "auth",
    resourceType: "system",
    environment: "production",
    severity: "info",
    details: {
      description: "Successful login from new device",
      metadata: { device: "MacBook Pro", location: "San Francisco, CA", ip: "192.168.1.xxx" },
    },
  },
  {
    id: "evt-008",
    timestamp: "5h ago",
    timestampFull: "2024-01-15 09:12:44 UTC",
    action: "workflow.failed",
    actionLabel: "Workflow Failed",
    actor: "system",
    actorType: "system",
    resource: "sync-customers",
    resourceType: "workflow",
    environment: "production",
    severity: "error",
    details: {
      description: "Automated run of sync-customers failed at step 3",
      metadata: { step: "3", error: "Connection timeout", duration: "4m 32s" },
    },
  },
]

const actionIcons: Record<string, typeof CheckCircle2> = {
  "approval.granted": CheckCircle2,
  "approval.denied": XCircle,
  "ai.action": Bot,
  "workflow.run": Workflow,
  "workflow.update": Settings,
  "workflow.failed": AlertTriangle,
  "connector.update": Shield,
  "user.login": LogIn,
}

const severityConfig = {
  info: { color: "text-foreground", dot: "bg-blue-500", bg: "bg-transparent" },
  warning: { color: "text-amber-400", dot: "bg-amber-500", bg: "bg-amber-500/5" },
  error: { color: "text-red-400", dot: "bg-red-500", bg: "bg-red-500/5" },
}

const actorTypeConfig = {
  user: { icon: User, color: "text-blue-400", bg: "bg-blue-500/10" },
  system: { icon: Settings, color: "text-zinc-400", bg: "bg-zinc-500/10" },
  ai: { icon: Bot, color: "text-violet-400", bg: "bg-violet-500/10" },
}

// Timeline Event Component
function TimelineEvent({ 
  event, 
  isExpanded, 
  onToggle,
  isFirst,
  isLast
}: { 
  event: AuditEvent
  isExpanded: boolean
  onToggle: () => void
  isFirst: boolean
  isLast: boolean
}) {
  const ActionIcon = actionIcons[event.action] || Settings
  const severityCfg = severityConfig[event.severity]
  const actorCfg = actorTypeConfig[event.actorType]
  const ActorIcon = actorCfg.icon

  return (
    <motion.div
      layout
      className="relative"
    >
      {/* Timeline line */}
      {!isLast && (
        <div className={cn(
          "absolute left-5 top-12 bottom-0 w-px",
          event.severity === "error" ? "bg-gradient-to-b from-red-500/50 to-border" : "bg-border"
        )} />
      )}
      
      {/* Event node */}
      <div 
        className={cn(
          "relative flex gap-4 py-3 px-2 rounded-lg cursor-pointer transition-all",
          isExpanded ? "bg-card" : "hover:bg-card/50",
          event.severity === "error" && "bg-red-500/5"
        )}
        onClick={onToggle}
      >
        {/* Timeline dot */}
        <div className="relative flex flex-col items-center">
          <div className={cn(
            "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all",
            event.severity === "error" 
              ? "border-red-500/50 bg-red-500/10 shadow-[0_0_15px_rgba(239,68,68,0.3)]" 
              : event.severity === "warning"
                ? "border-amber-500/50 bg-amber-500/10"
                : "border-border bg-secondary"
          )}>
            <ActionIcon className={cn(
              "h-4 w-4",
              event.severity === "error" ? "text-red-400" :
              event.severity === "warning" ? "text-amber-400" :
              "text-muted-foreground"
            )} />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4 mb-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn("text-sm font-medium", severityCfg.color)}>
                {event.actionLabel}
              </span>
              <EnvironmentBadge environment={event.environment} />
              {event.actorType === "ai" && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-500/10 text-violet-400">
                  <Bot className="h-2.5 w-2.5" />
                  AI
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
              <Clock className="h-3 w-3" />
              {event.timestamp}
              <ChevronDown className={cn(
                "h-3.5 w-3.5 transition-transform",
                isExpanded && "rotate-180"
              )} />
            </div>
          </div>

          <p className="text-xs text-muted-foreground mb-2 line-clamp-1">
            {event.details.description}
          </p>

          {/* Actor & Resource */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <div className={cn("h-5 w-5 rounded flex items-center justify-center", actorCfg.bg)}>
                <ActorIcon className={cn("h-3 w-3", actorCfg.color)} />
              </div>
              <span className="text-foreground">{event.actor}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="text-muted-foreground">on</span>
              <span className="font-mono text-foreground">{event.resource}</span>
            </span>
          </div>

          {/* Expanded details */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-4 pt-4 border-t border-border/50 space-y-3">
                  <div>
                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
                      Full Timestamp
                    </span>
                    <p className="text-sm text-foreground mt-0.5 font-mono">{event.timestampFull}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
                      Description
                    </span>
                    <p className="text-sm text-foreground mt-0.5">{event.details.description}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
                      Metadata
                    </span>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {Object.entries(event.details.metadata).map(([key, value]) => (
                        <span key={key} className="inline-flex items-center rounded-md bg-secondary px-2 py-1 text-xs">
                          <span className="text-muted-foreground mr-1">{key}:</span>
                          <span className="text-foreground font-mono">{value}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}

export default function AuditPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all")
  const [selectedActorType, setSelectedActorType] = useState<string>("all")
  const [selectedDateRange, setSelectedDateRange] = useState<string>("7d")
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR<{ events: AuditEvent[], total: number }>(
    `/api/audit`,
    fetcher,
    {
      fallbackData: { events: fallbackEvents, total: fallbackEvents.length },
      revalidateOnFocus: false,
    }
  )

  const events = data?.events ?? fallbackEvents

  // Filter events
  const filteredEvents = events.filter((event) => {
    if (selectedSeverity !== "all" && event.severity !== selectedSeverity) return false
    if (selectedActorType !== "all" && event.actorType !== selectedActorType) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        event.actionLabel.toLowerCase().includes(query) ||
        event.actor.toLowerCase().includes(query) ||
        event.resource.toLowerCase().includes(query) ||
        event.details.description.toLowerCase().includes(query)
      )
    }
    return true
  })

  // Stats
  const errorCount = events.filter(e => e.severity === "error").length
  const aiEventCount = events.filter(e => e.actorType === "ai").length

  return (
    <AppShell>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">Forensic Timeline</h1>
              <p className="text-sm text-muted-foreground mt-1">System investigation and event analysis</p>
            </div>
            <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => mutate()}>
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {/* Quick stats & filters */}
          <div className="flex items-center gap-4">
            {/* Stats */}
            <div className="flex items-center gap-3">
              {errorCount > 0 && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertTriangle className="h-3 w-3 text-red-400" />
                  <span className="text-xs font-medium text-red-400">{errorCount} errors</span>
                </div>
              )}
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-violet-500/10 border border-violet-500/20">
                <Bot className="h-3 w-3 text-violet-400" />
                <span className="text-xs font-medium text-violet-400">{aiEventCount} AI actions</span>
              </div>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 ml-auto">
              <Select value={selectedDateRange} onValueChange={setSelectedDateRange}>
                <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary border-border">
                  <Calendar className="h-3 w-3 mr-2 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24h">Last 24 hours</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                </SelectContent>
              </Select>

              <Select value={selectedSeverity} onValueChange={setSelectedSeverity}>
                <SelectTrigger className="w-[110px] h-8 text-xs bg-secondary border-border">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All levels</SelectItem>
                  <SelectItem value="error">Errors</SelectItem>
                  <SelectItem value="warning">Warnings</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>

              <Select value={selectedActorType} onValueChange={setSelectedActorType}>
                <SelectTrigger className="w-[110px] h-8 text-xs bg-secondary border-border">
                  <SelectValue placeholder="Actor" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actors</SelectItem>
                  <SelectItem value="user">Users</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                  <SelectItem value="ai">AI</SelectItem>
                </SelectContent>
              </Select>

              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Search events..."
                  className="pl-8 h-8 w-[200px] text-xs bg-secondary border-border"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5" />
            Failed to load. Showing cached data.
          </div>
        )}

        {/* Timeline */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4 animate-pulse">
                  <div className="h-10 w-10 rounded-full bg-secondary" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-48 bg-secondary rounded" />
                    <div className="h-3 w-full bg-secondary rounded" />
                    <div className="h-3 w-32 bg-secondary rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary mb-3">
                <Search className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">No events match your filters</p>
            </div>
          ) : (
            <div className="space-y-0">
              {filteredEvents.map((event, index) => (
                <TimelineEvent
                  key={event.id}
                  event={event}
                  isExpanded={expandedEvent === event.id}
                  onToggle={() => setExpandedEvent(expandedEvent === event.id ? null : event.id)}
                  isFirst={index === 0}
                  isLast={index === filteredEvents.length - 1}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {filteredEvents.length > 0 && (
          <div className="flex-shrink-0 border-t border-border px-6 py-3">
            <p className="text-xs text-muted-foreground">
              Showing {filteredEvents.length} of {events.length} events
            </p>
          </div>
        )}
      </div>
    </AppShell>
  )
}
