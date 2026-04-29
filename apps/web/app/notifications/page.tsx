"use client"

import { useState, useEffect } from "react"
import useSWR from "swr"
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
  ExternalLink,
  Clock,
  Trash2,
  MailOpen,
  Settings,
  UserPlus,
  AtSign,
  Rocket,
  AlertTriangle,
  UserCheck,
  Building2,
} from "lucide-react"
import Link from "next/link"
import { toast } from "sonner"
import { notificationsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import type { Notification as ApiNotification, NotificationType } from "@/types/api"

const typeConfig = {
  approval_needed: {
    icon: AlertCircle,
    color: "text-amber-500",
    bg: "bg-amber-500/10",
    label: "Approval",
  },
  assignment_created: {
    icon: UserCheck,
    color: "text-violet-500",
    bg: "bg-violet-500/10",
    label: "Assignment",
  },
  run_completed: {
    icon: CheckCircle2,
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
    label: "Run Complete",
  },
  run_failed: {
    icon: AlertTriangle,
    color: "text-red-500",
    bg: "bg-red-500/10",
    label: "Run Failed",
  },
  mention: {
    icon: AtSign,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    label: "Mention",
  },
  team_invite: {
    icon: UserPlus,
    color: "text-cyan-500",
    bg: "bg-cyan-500/10",
    label: "Team Invite",
  },
  system: {
    icon: Rocket,
    color: "text-muted-foreground",
    bg: "bg-secondary",
    label: "System",
  },
}

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return "Just now"
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
  const { user } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [filter, setFilter] = useState<"all" | "unread" | "read">("all")
  const [typeFilter, setTypeFilter] = useState<NotificationType | null>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const { data, isLoading, mutate } = useSWR(
    user ? ["notifications:list", filter] : null,
    () => notificationsApi.list({ unread_only: filter === "unread", limit: 200, offset: 0 })
  )

  const notifications: ApiNotification[] = data?.notifications ?? []

  const filteredNotifications = notifications.filter((n) => {
    if (filter === "read" && !n.is_read) return false
    if (typeFilter && n.type !== typeFilter) return false
    return true
  })

  const unreadCount = data?.unread_count ?? notifications.filter((n) => !n.is_read).length
  const todayCount = notifications.filter((n) => {
    const today = new Date()
    const createdAt = new Date(n.created_at)
    return !Number.isNaN(createdAt.getTime()) && createdAt.toDateString() === today.toDateString()
  }).length

  const markAsRead = async (id: string) => {
    try {
      await notificationsApi.markRead(id)
      await mutate((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          unread_count: Math.max(prev.unread_count - 1, 0),
          notifications: prev.notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
        }
      }, { revalidate: false })
    } catch (error) {
      console.error("Failed to mark as read", error)
      toast.error(error instanceof Error ? error.message : "Failed to mark as read")
    }
  }

  const markAllAsRead = async () => {
    try {
      await notificationsApi.markAllRead()
      await mutate((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          unread_count: 0,
          notifications: prev.notifications.map((n) => ({ ...n, is_read: true })),
        }
      }, { revalidate: false })
      toast.success("All notifications marked as read")
    } catch (error) {
      console.error("Failed to mark all as read", error)
      toast.error(error instanceof Error ? error.message : "Failed to mark all as read")
    }
  }

  const deleteNotification = async (id: string) => {
    try {
      await notificationsApi.delete(id)
      await mutate((prev) => {
        if (!prev) return prev
        const deleted = prev.notifications.find((n) => n.id === id)
        return {
          ...prev,
          unread_count: deleted && !deleted.is_read ? Math.max(prev.unread_count - 1, 0) : prev.unread_count,
          notifications: prev.notifications.filter((n) => n.id !== id),
        }
      }, { revalidate: false })
    } catch (error) {
      console.error("Failed to delete notification", error)
      toast.error(error instanceof Error ? error.message : "Failed to delete notification")
    }
  }

  const clearAll = async () => {
    if (notifications.length === 0) return
    try {
      const ids = notifications.map((n) => n.id)
      await Promise.allSettled(ids.map((id) => notificationsApi.archive(id)))
      await mutate((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          unread_count: 0,
          notifications: [],
        }
      }, { revalidate: false })
      toast.success("Notifications archived")
    } catch (error) {
      console.error("Failed to archive notifications", error)
      toast.error(error instanceof Error ? error.message : "Failed to archive notifications")
    }
  }

  if (!user) {
    return (
      <AppShell title="Notifications">
        <div className="flex items-center justify-center h-full p-8">
          <div className="text-center">
            <Building2 className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">Sign in required</p>
            <p className="text-xs text-muted-foreground mt-1">Sign in to view your notifications.</p>
          </div>
        </div>
      </AppShell>
    )
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
              {(Object.keys(typeConfig) as NotificationType[]).map((type) => {
                const config = typeConfig[type]
                return (
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
                )
              })}
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
            {isLoading && (
              <div className="px-4 py-6 text-sm text-muted-foreground">Loading notifications...</div>
            )}
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
                        !notification.is_read && "bg-primary/5"
                      )}
                    >
                      {/* Unread indicator */}
                      {!notification.is_read && (
                        <div className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-blue-500" />
                      )}

                      <Link 
                        href={notification.url || "/notifications"}
                        onClick={() => void markAsRead(notification.id)}
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
                                  notification.is_read ? "text-muted-foreground" : "text-foreground"
                                )}>
                                  {notification.title}
                                </p>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                  {notification.body}
                                </p>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatRelativeTime(notification.created_at)}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex items-start gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {!notification.is_read && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  void markAsRead(notification.id)
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
                                void deleteNotification(notification.id)
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
