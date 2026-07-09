"use client"

import { useState, useEffect, createContext, useContext, useCallback, useMemo } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { notificationsApi } from "@/lib/api"
import { apiFetch } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import type { Notification as ApiNotification, NotificationType } from "@/types/api"
import { 
  Bell, 
  X, 
  Check, 
  CheckCircle2, 
  AlertCircle, 
  Package, 
  Mail, 
  MessageSquare, 
  Database, 
  Download,
  ExternalLink,
  Clock,
  Sparkles,
  ArrowRight
} from "lucide-react"
import Link from "next/link"
import { toast } from "sonner"

// Notification types
export interface Notification {
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

function mapApiType(type: NotificationType): Notification["type"] {
  switch (type) {
    case "approval_needed":
      return "approval_required"
    case "run_failed":
      return "error"
    case "run_completed":
    case "assignment_created":
    case "agent_created":
    case "workflow_created":
    case "task_completed":
      return "task_complete"
    default:
      return "external_action"
  }
}

function mapApiNotification(row: ApiNotification): Notification {
  return {
    id: row.id,
    type: mapApiType(row.type),
    title: row.title,
    message: row.body,
    timestamp: new Date(row.created_at),
    read: row.is_read,
    link: row.url || undefined,
  }
}

// Context for global notification state
interface NotificationContextType {
  notifications: Notification[]
  unreadCount: number
  addNotification: (notification: Omit<Notification, "id" | "timestamp" | "read">) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearNotification: (id: string) => void
}

const NotificationContext = createContext<NotificationContextType | null>(null)

export function useNotifications() {
  const context = useContext(NotificationContext)
  return context
}

// Hook that throws if used outside provider - use when you require notifications
export function useNotificationsRequired() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error("useNotificationsRequired must be used within NotificationProvider")
  }
  return context
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const { data, mutate } = useSWR(
    user ? ["notification-center", user.id] : null,
    () => notificationsApi.list({ limit: 50, offset: 0 }),
    { refreshInterval: 60_000 }
  )

  useEffect(() => {
    if (!user) return
    const controller = new AbortController()
    let cancelled = false

    const handleSseChunk = (chunk: string) => {
      const lines = chunk.split("\n")
      let eventName = "message"
      let dataLine = ""
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim()
        if (line.startsWith("data:")) dataLine += line.slice(5).trim()
      }
      if (eventName !== "notification" || !dataLine) return
      try {
        const payload = JSON.parse(dataLine) as ApiNotification
        void mutate(
          (prev) => {
            if (!prev) return prev
            if (prev.notifications.some((row) => row.id === payload.id)) return prev
            const row: ApiNotification = {
              id: payload.id,
              type: (payload.type as NotificationType) || "system",
              title: payload.title || "Notification",
              body: payload.body || "",
              entity_type: payload.entity_type,
              entity_id: payload.entity_id,
              url: payload.url,
              is_read: false,
              is_archived: false,
              created_at: new Date().toISOString(),
            }
            toast.success(row.title, {
              description: row.body,
              ...(row.url ? { action: { label: "View", onClick: () => window.open(row.url, "_self") } } : {}),
            })
            return {
              notifications: [row, ...prev.notifications],
              unread_count: prev.unread_count + 1,
            }
          },
          { revalidate: false },
        )
      } catch {
        // ignore malformed SSE payloads
      }
    }

    async function connectStream() {
      let backoffMs = 3_000
      while (!cancelled) {
        try {
          const response = await apiFetch(notificationsApi.streamUrl(), {
            headers: { Accept: "text/event-stream" },
            signal: controller.signal,
          })
          if (response.status === 404 || response.status === 405 || response.status === 501) {
            return
          }
          if (!response.ok || !response.body) {
            await new Promise((resolve) => setTimeout(resolve, backoffMs))
            backoffMs = Math.min(backoffMs * 2, 60_000)
            continue
          }
          backoffMs = 3_000
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ""
          while (!cancelled) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const parts = buffer.split("\n\n")
            buffer = parts.pop() ?? ""
            for (const part of parts) {
              if (part.startsWith(":")) continue
              handleSseChunk(part)
            }
          }
        } catch {
          if (cancelled || controller.signal.aborted) break
        }
        if (!cancelled) {
          await new Promise((resolve) => setTimeout(resolve, backoffMs))
          backoffMs = Math.min(backoffMs * 2, 60_000)
        }
      }
    }

    void connectStream()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [user, mutate])

  const notifications = useMemo(
    () => (data?.notifications ?? []).map(mapApiNotification),
    [data?.notifications]
  )

  const addNotification = useCallback((notification: Omit<Notification, "id" | "timestamp" | "read">) => {
    const newNotification: Notification = {
      ...notification,
      id: `local-${Date.now()}`,
      timestamp: new Date(),
      read: false,
    }
    if (notification.type === "task_complete") {
      toast.success(notification.title, {
        description: notification.message,
        ...(notification.link ? { action: { label: "View", onClick: () => window.open(notification.link, "_self") } } : {}),
      })
    }
    void mutate(
      (prev) => ({
        notifications: [
          {
            id: newNotification.id,
            type: "system" as NotificationType,
            title: newNotification.title,
            body: newNotification.message,
            url: newNotification.link,
            is_read: false,
            is_archived: false,
            created_at: newNotification.timestamp.toISOString(),
          },
          ...(prev?.notifications ?? []),
        ],
        unread_count: (prev?.unread_count ?? 0) + 1,
      }),
      { revalidate: false }
    )
  }, [mutate])

  const markAsRead = useCallback(async (id: string) => {
    if (!id.startsWith("local-")) {
      try {
        await notificationsApi.markRead(id)
      } catch {
        return
      }
    }
    void mutate(
      (prev) => {
        if (!prev) return prev
        const target = prev.notifications.find((row) => row.id === id)
        return {
          ...prev,
          unread_count:
            target && !target.is_read ? Math.max(prev.unread_count - 1, 0) : prev.unread_count,
          notifications: prev.notifications.map((row) =>
            row.id === id ? { ...row, is_read: true } : row
          ),
        }
      },
      { revalidate: false }
    )
  }, [mutate])

  const markAllAsRead = useCallback(async () => {
    try {
      await notificationsApi.markAllRead()
    } catch {
      return
    }
    void mutate(
      (prev) =>
        prev
          ? {
              ...prev,
              unread_count: 0,
              notifications: prev.notifications.map((row) => ({ ...row, is_read: true })),
            }
          : prev,
      { revalidate: false }
    )
  }, [mutate])

  const clearNotification = useCallback(async (id: string) => {
    if (!id.startsWith("local-")) {
      try {
        await notificationsApi.archive(id)
      } catch {
        return
      }
    }
    void mutate(
      (prev) => {
        if (!prev) return prev
        const target = prev.notifications.find((row) => row.id === id)
        return {
          ...prev,
          unread_count:
            target && !target.is_read ? Math.max(prev.unread_count - 1, 0) : prev.unread_count,
          notifications: prev.notifications.filter((row) => row.id !== id),
        }
      },
      { revalidate: false }
    )
  }, [mutate])

  const unreadCount = data?.unread_count ?? notifications.filter((n) => !n.read).length

  return (
    <NotificationContext.Provider value={{ 
      notifications, 
      unreadCount, 
      addNotification, 
      markAsRead, 
      markAllAsRead,
      clearNotification 
    }}>
      {children}
    </NotificationContext.Provider>
  )
}

// Platform icon mapping
const platformIcons: Record<string, React.ElementType> = {
  Email: Mail,
  Slack: MessageSquare,
  HubSpot: Database,
  CRM: Database,
  Gravitre: Package,
  Download: Download,
}

// Notification type icons and colors
const typeConfig = {
  task_complete: { 
    icon: CheckCircle2, 
    color: "text-emerald-500", 
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20"
  },
  output_delivered: { 
    icon: Package, 
    color: "text-blue-500", 
    bg: "bg-blue-500/10",
    border: "border-blue-500/20"
  },
  external_action: { 
    icon: ExternalLink, 
    color: "text-violet-500", 
    bg: "bg-violet-500/10",
    border: "border-violet-500/20"
  },
  approval_required: { 
    icon: AlertCircle, 
    color: "text-amber-500", 
    bg: "bg-amber-500/10",
    border: "border-amber-500/20"
  },
  error: { 
    icon: AlertCircle, 
    color: "text-red-500", 
    bg: "bg-red-500/10",
    border: "border-red-500/20"
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

// Individual notification item
function NotificationItem({ 
  notification, 
  onRead, 
  onClear 
}: { 
  notification: Notification
  onRead: () => void
  onClear: () => void
}) {
  const config = typeConfig[notification.type]
  const Icon = config.icon

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className={cn(
        "relative p-4 border-b border-border/50 transition-colors hover:bg-secondary/30",
        !notification.read && "bg-primary/5"
      )}
    >
      {/* Unread indicator */}
      {!notification.read && (
        <div className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-blue-500" />
      )}

      <Link 
        href={notification.link || "/notifications"} 
        onClick={onRead}
        className="block"
      >
        <div className="flex gap-3">
          {/* Icon */}
          <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0", config.bg)}>
            <Icon className={cn("w-4 h-4", config.color)} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <p className={cn(
                "text-sm font-medium",
                notification.read ? "text-muted-foreground" : "text-foreground"
              )}>
                {notification.title}
              </p>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(notification.timestamp)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
              {notification.message}
            </p>

            {/* Actions taken */}
            {notification.actions && notification.actions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {notification.actions.map((action, i) => {
                  const ActionIcon = platformIcons[action.platform] || Package
                  return (
                    <span 
                      key={i}
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]",
                        action.status === "success" && "bg-emerald-500/10 text-emerald-500",
                        action.status === "failed" && "bg-red-500/10 text-red-500",
                        action.status === "pending" && "bg-amber-500/10 text-amber-500"
                      )}
                    >
                      <ActionIcon className="w-2.5 h-2.5" />
                      {action.description}
                    </span>
                  )
                })}
              </div>
            )}
          </div>

          {/* Clear button */}
          <button
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onClear()
            }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-secondary transition-opacity"
          >
            <X className="w-3 h-3 text-muted-foreground" />
          </button>
        </div>
      </Link>
    </motion.div>
  )
}

// Main Notification Center Component
export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false)
  const context = useNotifications()

  const notifications = context?.notifications ?? []
  const unreadCount = context?.unreadCount ?? 0
  const markAsRead = context?.markAsRead ?? (() => {})
  const markAllAsRead = context?.markAllAsRead ?? (() => {})
  const clearNotification = context?.clearNotification ?? (() => {})

  return (
    <div className="relative">
      {/* Bell Button */}
      <Button 
        variant="ghost" 
        size="icon" 
        className="h-8 w-8 hover:bg-accent relative group"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell className="h-4 w-4 text-muted-foreground transition-transform group-hover:rotate-12" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
          </span>
        )}
      </Button>

      {/* Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />

            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, y: -10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full mt-2 z-50 w-[calc(100vw-2rem)] sm:w-96 max-w-[400px] rounded-xl border border-border bg-card shadow-2xl overflow-hidden"
            >
              {/* Header */}
              <div className="px-4 py-3 border-b border-border bg-gradient-to-r from-secondary/50 to-transparent">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">Notifications</span>
                    {unreadCount > 0 && (
                      <Badge variant="secondary" className="h-5 px-1.5 text-[10px] bg-blue-500/10 text-blue-500">
                        {unreadCount} new
                      </Badge>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1"
                      onClick={markAllAsRead}
                    >
                      <Check className="h-3 w-3" />
                      Mark all read
                    </Button>
                  )}
                </div>
              </div>

              {/* Notification List */}
              <div className="max-h-[60vh] overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="py-12 text-center">
                    <div className="w-12 h-12 rounded-full bg-secondary/50 flex items-center justify-center mx-auto mb-3">
                      <Bell className="w-5 h-5 text-muted-foreground/50" />
                    </div>
                    <p className="text-sm text-muted-foreground">No notifications yet</p>
                  </div>
                ) : (
                  <div className="group">
                    <AnimatePresence>
                      {notifications.map((notification) => (
                        <NotificationItem
                          key={notification.id}
                          notification={notification}
                          onRead={() => markAsRead(notification.id)}
                          onClear={() => clearNotification(notification.id)}
                        />
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-border bg-secondary/30 p-2">
                <Link href="/notifications" onClick={() => setIsOpen(false)}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="w-full justify-center text-xs text-muted-foreground hover:text-foreground gap-1"
                  >
                    View all notifications
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// Toast notification for real-time alerts
export function NotificationToast({ 
  notification, 
  onDismiss 
}: { 
  notification: Notification
  onDismiss: () => void
}) {
  const config = typeConfig[notification.type]
  const Icon = config.icon

  useEffect(() => {
    const timer = setTimeout(onDismiss, 5000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.9 }}
      className={cn(
        "fixed bottom-4 right-4 z-50 w-80 rounded-xl border bg-card shadow-2xl overflow-hidden",
        config.border
      )}
    >
      <div className="p-4">
        <div className="flex gap-3">
          <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0", config.bg)}>
            <Icon className={cn("w-4 h-4", config.color)} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">{notification.title}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{notification.message}</p>
            
            {notification.actions && notification.actions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {notification.actions.slice(0, 2).map((action, i) => {
                  const ActionIcon = platformIcons[action.platform] || Package
                  return (
                    <span 
                      key={i}
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]",
                        action.status === "success" && "bg-emerald-500/10 text-emerald-500"
                      )}
                    >
                      <ActionIcon className="w-2.5 h-2.5" />
                      {action.description}
                    </span>
                  )
                })}
              </div>
            )}
          </div>
          <button
            onClick={onDismiss}
            className="p-1 rounded hover:bg-secondary transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <motion.div
        initial={{ scaleX: 1 }}
        animate={{ scaleX: 0 }}
        transition={{ duration: 5, ease: "linear" }}
        className={cn("h-1 origin-left", config.bg.replace("/10", ""))}
      />
    </motion.div>
  )
}
