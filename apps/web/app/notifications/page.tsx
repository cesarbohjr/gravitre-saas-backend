"use client"

import { useRef, useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  Bell,
  Check,
  CheckCircle2,
  AlertCircle,
  Clock,
  Trash2,
  MailOpen,
  Settings,
  Archive,
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
    color: "text-warning",
    bg: "bg-warning/10",
    label: "Approval",
  },
  assignment_created: {
    icon: UserCheck,
    color: "text-[color:var(--g-signal)]",
    bg: "bg-[color:var(--g-signal-surface)]",
    label: "Assignment",
  },
  run_completed: {
    icon: CheckCircle2,
    color: "text-success",
    bg: "bg-success/10",
    label: "Run complete",
  },
  run_failed: {
    icon: AlertTriangle,
    color: "text-destructive",
    bg: "bg-destructive/10",
    label: "Run failed",
  },
  mention: {
    icon: AtSign,
    color: "text-[color:var(--g-signal)]",
    bg: "bg-[color:var(--g-signal-surface)]",
    label: "Mention",
  },
  team_invite: {
    icon: UserPlus,
    color: "text-[color:var(--g-brand)]",
    bg: "bg-[color:var(--g-brand-soft)]",
    label: "Team invite",
  },
  system: {
    icon: Rocket,
    color: "text-muted-foreground",
    bg: "bg-secondary",
    label: "System",
  },
  agent_created: {
    icon: CheckCircle2,
    color: "text-success",
    bg: "bg-success/10",
    label: "Agent created",
  },
  workflow_created: {
    icon: CheckCircle2,
    color: "text-success",
    bg: "bg-success/10",
    label: "Workflow created",
  },
  task_completed: {
    icon: CheckCircle2,
    color: "text-success",
    bg: "bg-success/10",
    label: "Task complete",
  },
}

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return "Time not reported"
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
  const reduceMotion = useReducedMotion()
  const [filter, setFilter] = useState<"all" | "unread" | "read">("all")
  const [typeFilter, setTypeFilter] = useState<NotificationType | null>(null)
  const [pending, setPending] = useState(false)
  const operationInFlight = useRef(false)

  const { data, error, isLoading, mutate } = useSWR(
    user ? ["notifications:list", user.id, filter] : null,
    () => notificationsApi.list({ unread_only: filter === "unread", limit: 200, offset: 0 })
  )
  const notifications: ApiNotification[] = data?.notifications ?? []
  const filteredNotifications = notifications.filter((n) => {
    if (filter === "read" && !n.is_read) return false
    if (filter === "unread" && n.is_read) return false
    return !typeFilter || n.type === typeFilter
  })
  const unreadCount = typeof data?.unread_count === "number" && Number.isFinite(data.unread_count)
    ? data.unread_count : null
  const todayCount = notifications.filter((n) => {
    const createdAt = new Date(n.created_at)
    return createdAt.toDateString() === new Date().toDateString()
  }).length
  const metricUnavailable = isLoading ? "—" : "Not reported"

  // Serialize inbox mutations, including rapid repeated clicks before React renders.
  const perform = async (operation: () => Promise<void>) => {
    if (operationInFlight.current) return
    operationInFlight.current = true
    setPending(true)
    try {
      await operation()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update notifications")
    } finally {
      operationInFlight.current = false
      setPending(false)
    }
  }
  const markAsRead = (id: string) => {
    if (error || !notifications.some((n) => n.id === id && !n.is_read)) return
    return perform(async () => {
      await notificationsApi.markRead(id)
      await mutate((prev) => {
        if (!prev) return prev
        const wasUnread = prev.notifications.some((n) => n.id === id && !n.is_read)
        return {
          ...prev,
          unread_count: wasUnread ? Math.max(prev.unread_count - 1, 0) : prev.unread_count,
          notifications: prev.notifications.map((n) => n.id === id ? { ...n, is_read: true } : n),
        }
      }, { revalidate: false })
    })
  }
  const markAllAsRead = () => perform(async () => {
    await notificationsApi.markAllRead()
    await mutate((prev) => prev ? {
      ...prev, unread_count: 0,
      notifications: prev.notifications.map((n) => ({ ...n, is_read: true })),
    } : prev, { revalidate: false })
    toast.success("All notifications marked as read")
  })
  const deleteNotification = (id: string) => perform(async () => {
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
  })
  const archiveLoaded = () => perform(async () => {
    const ids = notifications.map((n) => n.id)
    const results = await Promise.allSettled(ids.map((id) => notificationsApi.archive(id)))
    const archived = new Set(ids.filter((_, index) => results[index].status === "fulfilled"))
    await mutate((prev) => {
      if (!prev) return prev
      const removedUnread = prev.notifications.filter((n) => archived.has(n.id) && !n.is_read).length
      return {
        ...prev,
        unread_count: Math.max(prev.unread_count - removedUnread, 0),
        notifications: prev.notifications.filter((n) => !archived.has(n.id)),
      }
    }, { revalidate: false })
    const failed = ids.length - archived.size
    if (failed) toast.error(`${failed} notification${failed === 1 ? "" : "s"} could not be archived. Try again.`)
    else toast.success("Loaded notifications archived")
  })

  if (!user) {
    return (
      <AppShell title="Notifications">
        <div className="flex h-full items-center justify-center p-8 text-center">
          <div>
            <Building2 className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">Sign in required</p>
            <p className="mt-1 text-xs text-muted-foreground">Sign in to view your notifications.</p>
          </div>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Notifications">
      <div className="flex h-full min-h-0 flex-col" data-composition="operate">
        <GravitrePageHeader
          title="Notifications"
          description="Review updates, open the work, and resolve what needs your attention."
          family="operating"
          icon={<Bell className="h-5 w-5" />}
          actions={<>
            <Button variant="outline" className="min-h-11 gap-2" onClick={markAllAsRead}
              disabled={pending || isLoading || !!error || unreadCount === null || unreadCount === 0}>
              <MailOpen className="h-4 w-4" />Mark all read
            </Button>
            <Button asChild variant="ghost" className="min-h-11 gap-2">
              <Link href="/settings?section=notifications"><Settings className="h-4 w-4" />Settings</Link>
            </Button>
          </>}
        >
          <section aria-label="Inbox summary" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <GravitreMetric label="Unread" value={error ? "Not reported" : unreadCount ?? metricUnavailable}
              hint="Across your inbox" warning={!error && (unreadCount ?? 0) > 0} />
            <GravitreMetric label="Today in loaded results" value={data && !error ? todayCount : metricUnavailable} />
            <GravitreMetric label="Loaded notifications" value={data && !error ? notifications.length : metricUnavailable} />
          </section>
        </GravitrePageHeader>

        <div className="flex min-h-0 flex-1 flex-col px-4 pb-4 sm:px-6">
          <div className="flex flex-wrap items-center gap-3 py-3">
            <div role="group" aria-label="Read status" className="flex rounded-lg border border-border bg-card p-1">
              {(["all", "unread", "read"] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f} disabled={pending}
                  className={cn("min-h-11 rounded-md px-3 text-sm font-medium capitalize transition-colors disabled:opacity-50 motion-reduce:transition-none",
                    filter === f ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)]" : "text-muted-foreground hover:text-foreground")}>
                  {f}
                  {f === "unread" && !error && (unreadCount ?? 0) > 0 && <Badge variant="secondary" className="ml-1.5">{unreadCount}</Badge>}
                </button>
              ))}
            </div>
            <label className="flex min-h-11 items-center gap-2 text-sm text-muted-foreground">
              Type
              <select aria-label="Notification type" value={typeFilter ?? "all"} disabled={pending}
                onChange={(event) => setTypeFilter(event.target.value === "all" ? null : event.target.value as NotificationType)}
                className="min-h-11 max-w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground">
                <option value="all">All types</option>
                {(Object.keys(typeConfig) as NotificationType[]).map((type) => <option key={type} value={type}>{typeConfig[type].label}</option>)}
              </select>
            </label>
            {notifications.length > 0 && <Button variant="ghost" className="min-h-11 gap-2 sm:ml-auto"
              disabled={pending || !!error} onClick={archiveLoaded}><Archive className="h-4 w-4" />Archive loaded</Button>}
          </div>
          <p className="mb-3 text-xs text-muted-foreground">Showing up to 200 recent notifications. Type and read filters apply to loaded results; unread count covers your inbox.</p>
          {error && <div role="alert" className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-card p-4">
            <p className="text-sm">Could not load notifications. {data ? "Showing previously loaded updates." : "Try again to see your inbox."}</p>
            <Button variant="outline" className="min-h-11" onClick={() => void mutate()} disabled={pending}>Retry</Button>
          </div>}
          <div aria-label="Notifications" aria-busy={isLoading || pending} className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-border bg-card">
            {isLoading ? <p role="status" className="p-6 text-sm text-muted-foreground">Loading notifications...</p>
              : filteredNotifications.length === 0 ? (!error && <div className="px-4 py-16 text-center">
                <Bell className="mx-auto mb-4 h-7 w-7 text-muted-foreground" />
                <p className="text-sm font-medium">{filter !== "all" || typeFilter ? "No matching notifications" : "No notifications"}</p>
                <p className="mt-1 text-sm text-muted-foreground">{filter !== "all" || typeFilter ? "Try changing your filters." : "Your recent inbox is empty."}</p>
              </div>) : <AnimatePresence initial={false}>
                {filteredNotifications.map((notification) => {
                  const config = typeConfig[notification.type] ?? typeConfig.system
                  const Icon = config.icon
                  return <motion.article key={notification.id} data-notification-id={notification.id}
                    initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }}
                    exit={reduceMotion ? undefined : { opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.18 }}
                    className={cn("flex flex-col gap-2 border-b border-border p-4 last:border-b-0 sm:flex-row sm:items-start sm:gap-4",
                      !notification.is_read && "bg-[color:var(--g-brand-soft)]/30")}>
                    <Link href={notification.url || "/notifications"} onClick={() => void markAsRead(notification.id)}
                      className="flex min-w-0 flex-1 gap-3 rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--g-brand)]">
                      <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", config.bg)}><Icon className={cn("h-5 w-5", config.color)} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <span>{config.label}</span><span className={!notification.is_read ? "font-medium text-[color:var(--g-brand-active)]" : undefined}>{notification.is_read ? "Read" : "Unread"}</span>
                          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{formatRelativeTime(notification.created_at)}</span>
                        </div>
                        <p className="break-words text-sm font-medium [overflow-wrap:anywhere]">{notification.title}</p>
                        <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">{notification.body}</p>
                      </div>
                    </Link>
                    <div className="flex shrink-0 items-center gap-1 pl-[52px] sm:pl-0">
                      {!notification.is_read && <Button variant="ghost" className="min-h-11 min-w-11 gap-1.5 px-2"
                        aria-label={`Mark as read: ${notification.title}`} disabled={pending || !!error} onClick={() => void markAsRead(notification.id)}>
                        <Check className="h-4 w-4" /><span className="sm:sr-only">Mark read</span>
                      </Button>}
                      <Button variant="ghost" className="min-h-11 min-w-11 gap-1.5 px-2 hover:text-destructive"
                        aria-label={`Delete notification: ${notification.title}`} disabled={pending || !!error} onClick={() => void deleteNotification(notification.id)}>
                        <Trash2 className="h-4 w-4" /><span className="sm:sr-only">Delete</span>
                      </Button>
                    </div>
                  </motion.article>
                })}
              </AnimatePresence>}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
