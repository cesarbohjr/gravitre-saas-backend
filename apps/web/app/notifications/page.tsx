"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { 
  Bell, 
  Check, 
  CheckCircle2, 
  AlertCircle, 
  Package, 
  Mail, 
  MessageSquare, 
  Database, 
  ExternalLink,
  Clock,
  Trash2,
  Filter,
  Archive,
  MailOpen,
  Settings
} from "lucide-react"
import Link from "next/link"

// Notification types (shared with notification-center)
interface Notification {
  id: string
  type: "task_complete" | "output_delivered" | "external_action" | "approval_required" | "error"
  title: string
  message: string
  timestamp: Date
  read: boolean
  deliverable?: {
    id: string
    title: string
    type: string
  }
  actions?: {
    platform: string
    description: string
    status: "success" | "failed" | "pending"
  }[]
  link?: string
}

// Extended sample notifications
const allNotifications: Notification[] = [
  {
    id: "n1",
    type: "task_complete",
    title: "Task completed",
    message: "Q3 Healthcare Campaign is ready for review",
    timestamp: new Date(Date.now() - 1000 * 60 * 2),
    read: false,
    deliverable: { id: "d1", title: "Email Sequence - Product Launch", type: "emails" },
    actions: [
      { platform: "Gravitre", description: "Stored in Deliverables", status: "success" },
    ],
    link: "/lite/deliverables",
  },
  {
    id: "n2",
    type: "output_delivered",
    title: "Output delivered",
    message: "Campaign sent to your email",
    timestamp: new Date(Date.now() - 1000 * 60 * 15),
    read: false,
    deliverable: { id: "d2", title: "Enterprise Segment", type: "segment" },
    actions: [
      { platform: "Email", description: "Sent to your inbox", status: "success" },
      { platform: "Gravitre", description: "Stored in Deliverables", status: "success" },
    ],
    link: "/lite/deliverables",
  },
  {
    id: "n3",
    type: "external_action",
    title: "Posted to Slack",
    message: "Campaign summary shared in #marketing",
    timestamp: new Date(Date.now() - 1000 * 60 * 45),
    read: true,
    actions: [
      { platform: "Slack", description: "Posted to #marketing", status: "success" },
    ],
    link: "/lite/deliverables",
  },
  {
    id: "n4",
    type: "external_action",
    title: "Created in HubSpot",
    message: "New campaign created in your CRM",
    timestamp: new Date(Date.now() - 1000 * 60 * 60),
    read: true,
    actions: [
      { platform: "HubSpot", description: "Campaign created", status: "success" },
    ],
    link: "/lite/deliverables",
  },
  {
    id: "n5",
    type: "approval_required",
    title: "Approval needed",
    message: "Data sync workflow requires your approval before proceeding",
    timestamp: new Date(Date.now() - 1000 * 60 * 90),
    read: false,
    link: "/approvals",
  },
  {
    id: "n6",
    type: "task_complete",
    title: "Workflow completed",
    message: "Weekly analytics report has finished processing",
    timestamp: new Date(Date.now() - 1000 * 60 * 120),
    read: true,
    deliverable: { id: "d3", title: "Weekly Analytics Report", type: "report" },
    actions: [
      { platform: "Email", description: "Sent to team", status: "success" },
    ],
    link: "/lite/deliverables",
  },
  {
    id: "n7",
    type: "error",
    title: "Sync failed",
    message: "Salesforce data sync encountered an error",
    timestamp: new Date(Date.now() - 1000 * 60 * 180),
    read: true,
    actions: [
      { platform: "Salesforce", description: "Connection timeout", status: "failed" },
    ],
    link: "/sources",
  },
  {
    id: "n8",
    type: "output_delivered",
    title: "Report ready",
    message: "Monthly performance dashboard exported",
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4),
    read: true,
    deliverable: { id: "d4", title: "Performance Dashboard", type: "dashboard" },
    actions: [
      { platform: "Gravitre", description: "Available for download", status: "success" },
    ],
    link: "/lite/deliverables",
  },
]

// Platform icon mapping
const platformIcons: Record<string, React.ElementType> = {
  Email: Mail,
  Slack: MessageSquare,
  HubSpot: Database,
  Salesforce: Database,
  CRM: Database,
  Gravitre: Package,
}

// Notification type config
const typeConfig = {
  task_complete: { 
    icon: CheckCircle2, 
    color: "text-emerald-500", 
    bg: "bg-emerald-500/10",
    label: "Completed"
  },
  output_delivered: { 
    icon: Package, 
    color: "text-blue-500", 
    bg: "bg-blue-500/10",
    label: "Delivered"
  },
  external_action: { 
    icon: ExternalLink, 
    color: "text-violet-500", 
    bg: "bg-violet-500/10",
    label: "External"
  },
  approval_required: { 
    icon: AlertCircle, 
    color: "text-amber-500", 
    bg: "bg-amber-500/10",
    label: "Approval"
  },
  error: { 
    icon: AlertCircle, 
    color: "text-red-500", 
    bg: "bg-red-500/10",
    label: "Error"
  },
}

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export default function NotificationsPage() {
  const [mounted, setMounted] = useState(false)
  const [notifications, setNotifications] = useState(allNotifications)
  const [filter, setFilter] = useState<"all" | "unread" | "read">("all")
  const [typeFilter, setTypeFilter] = useState<string | null>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const filteredNotifications = notifications.filter(n => {
    if (filter === "unread" && n.read) return false
    if (filter === "read" && !n.read) return false
    if (typeFilter && n.type !== typeFilter) return false
    return true
  })

  const unreadCount = notifications.filter(n => !n.read).length
  const todayCount = notifications.filter(n => {
    const today = new Date()
    return n.timestamp.toDateString() === today.toDateString()
  }).length

  const markAsRead = (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n))
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  const clearAll = () => {
    setNotifications([])
  }

  return (
    <AppShell title="Notifications">
      <div className="flex flex-col h-full">
        <PageHeader
          title="Notifications"
          description="Stay updated on your workflows and deliverables"
          icon={Bell}
          iconColor="from-blue-500/20 to-cyan-500/20"
          actions={
            <>
              <Button 
                variant="outline" 
                size="sm" 
                className="gap-2"
                onClick={markAllAsRead}
                disabled={unreadCount === 0}
              >
                <MailOpen className="h-4 w-4" />
                <span className="hidden sm:inline">Mark all read</span>
              </Button>
              <Link href="/settings?section=notifications">
                <Button variant="outline" size="sm" className="gap-2">
                  <Settings className="h-4 w-4" />
                  <span className="hidden sm:inline">Settings</span>
                </Button>
              </Link>
            </>
          }
        >
          <StatsGrid columns={3}>
            <StatCard label="Unread" value={unreadCount} variant={unreadCount > 0 ? "warning" : "default"} />
            <StatCard label="Today" value={todayCount} variant="info" />
            <StatCard label="Total" value={notifications.length} />
          </StatsGrid>
        </PageHeader>

        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Filters */}
          <div className="px-4 py-3 border-b border-border flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 p-1 rounded-lg bg-secondary/50 border border-border/50">
              {(["all", "unread", "read"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize",
                    filter === f
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {f}
                  {f === "unread" && unreadCount > 0 && (
                    <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-[10px]">
                      {unreadCount}
                    </Badge>
                  )}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
              {Object.entries(typeConfig).map(([type, config]) => (
                <button
                  key={type}
                  onClick={() => setTypeFilter(typeFilter === type ? null : type)}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors border",
                    typeFilter === type
                      ? `${config.bg} ${config.color} border-current`
                      : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/20"
                  )}
                >
                  <config.icon className="h-3 w-3" />
                  {config.label}
                </button>
              ))}
            </div>

            {notifications.length > 0 && (
              <Button 
                variant="ghost" 
                size="sm" 
                className="ml-auto gap-1.5 text-muted-foreground hover:text-destructive"
                onClick={clearAll}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear all
              </Button>
            )}
          </div>

          {/* Notification List */}
          <div className="flex-1 overflow-y-auto scrollbar-on-hover">
            {filteredNotifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-16">
                <div className="w-16 h-16 rounded-full bg-secondary/50 flex items-center justify-center mb-4">
                  <Bell className="w-7 h-7 text-muted-foreground/50" />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">No notifications</p>
                <p className="text-xs text-muted-foreground">
                  {filter !== "all" ? "Try changing your filters" : "You're all caught up!"}
                </p>
              </div>
            ) : (
              <AnimatePresence mode="popLayout">
                {filteredNotifications.map((notification, index) => {
                  const config = typeConfig[notification.type]
                  const Icon = config.icon

                  return (
                    <motion.div
                      key={notification.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ delay: mounted ? 0 : index * 0.05 }}
                      className={cn(
                        "relative border-b border-border/50 transition-colors hover:bg-secondary/30 group",
                        !notification.read && "bg-primary/5"
                      )}
                    >
                      {/* Unread indicator */}
                      {!notification.read && (
                        <div className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-blue-500" />
                      )}

                      <Link 
                        href={notification.link || "/lite/deliverables"} 
                        onClick={() => markAsRead(notification.id)}
                        className="block px-4 py-4 pl-6"
                      >
                        <div className="flex gap-4">
                          {/* Icon */}
                          <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0", config.bg)}>
                            <Icon className={cn("w-5 h-5", config.color)} />
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className={cn(
                                  "text-sm font-medium",
                                  notification.read ? "text-muted-foreground" : "text-foreground"
                                )}>
                                  {notification.title}
                                </p>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                  {notification.message}
                                </p>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatRelativeTime(notification.timestamp)}
                                </span>
                              </div>
                            </div>

                            {/* Actions taken */}
                            {notification.actions && notification.actions.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-3">
                                {notification.actions.map((action, i) => {
                                  const ActionIcon = platformIcons[action.platform] || Package
                                  return (
                                    <span 
                                      key={i}
                                      className={cn(
                                        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs",
                                        action.status === "success" && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
                                        action.status === "failed" && "bg-red-500/10 text-red-600 dark:text-red-400",
                                        action.status === "pending" && "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                                      )}
                                    >
                                      <ActionIcon className="w-3 h-3" />
                                      {action.description}
                                    </span>
                                  )
                                })}
                              </div>
                            )}

                            {/* Deliverable link */}
                            {notification.deliverable && (
                              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/50 border border-border/50">
                                <Package className="w-3.5 h-3.5 text-muted-foreground" />
                                <span className="text-xs text-foreground">{notification.deliverable.title}</span>
                                <Badge variant="secondary" className="text-[10px] px-1.5">
                                  {notification.deliverable.type}
                                </Badge>
                              </div>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex items-start gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {!notification.read && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  markAsRead(notification.id)
                                }}
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 hover:text-destructive"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                deleteNotification(notification.id)
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </Link>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
