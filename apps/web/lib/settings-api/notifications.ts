/**
 * Settings > Notifications: the per-person matrix and quiet hours
 * (/api/notifications/preferences), plus the Slack connection check
 * (/api/connectors). Rows are only the events the backend delivers today.
 */
import { fetcher } from "@/lib/fetcher"
import type { NotificationChannelPreference } from "@/lib/api"
import { sendJson } from "./security"

export type Channel = keyof NotificationChannelPreference
export type Matrix = Record<string, NotificationChannelPreference>

export interface QuietHours {
  enabled: boolean
  from: string
  to: string
  timezone: string
}

export interface NotificationEventRow {
  id: string
  label: string
  hint: string
  dot: "amber" | "red" | "green" | "ghost"
}

export const NOTIFICATION_GROUPS: Array<{ label: string; rows: NotificationEventRow[] }> = [
  {
    label: "Needs you",
    rows: [{ id: "approval_needed", label: "A request is waiting on you", hint: "Approvals and decisions", dot: "amber" }],
  },
  {
    label: "Runs and sources",
    rows: [
      { id: "run_failed", label: "A run failed", hint: "Workflows, plays and schedules", dot: "red" },
      { id: "source_attention", label: "A source needs attention", hint: "Expired sign in or sync error", dot: "red" },
      { id: "run_completed", label: "A run finished", hint: "Workflow and agent runs you started", dot: "green" },
    ],
  },
  {
    label: "Digests",
    rows: [{ id: "weekly_summary", label: "Weekly summary", hint: "Mondays at 09:00, workspace time", dot: "ghost" }],
  },
]

export const NOTIFICATION_EVENTS: NotificationEventRow[] = NOTIFICATION_GROUPS.flatMap((group) => group.rows)

export const CHANNELS: Array<{ key: Channel; label: string; aria: string }> = [
  { key: "email_enabled", label: "Email", aria: "by email" },
  { key: "slack_enabled", label: "Slack", aria: "in Slack" },
  { key: "bell_enabled", label: "In app", aria: "in app" },
]

/** Mirrors DEFAULT_EVENT_PREFERENCES in notification_preference_service.py; the API's `defaults` wins when present. */
export const FALLBACK_DEFAULTS: Matrix = {
  approval_needed: { email_enabled: true, slack_enabled: false, bell_enabled: true },
  run_failed: { email_enabled: true, slack_enabled: false, bell_enabled: true },
  source_attention: { email_enabled: true, slack_enabled: false, bell_enabled: true },
  run_completed: { email_enabled: false, slack_enabled: false, bell_enabled: true },
  weekly_summary: { email_enabled: false, slack_enabled: false, bell_enabled: true },
}

export const DEFAULT_QUIET: QuietHours = { enabled: false, from: "20:00", to: "08:00", timezone: "UTC" }

export const HOURS: string[] = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, "0")}:00`)

export const PREFERENCES_KEY = "notification-event-preferences"
export const CONNECTORS_KEY = "/api/connectors"

export interface PreferencesPayload {
  preferences: Matrix
  quietHours?: QuietHours
  defaults?: Matrix
}

export const notificationPrefsApi = {
  get: () => fetcher<PreferencesPayload>("/api/notifications/preferences"),
  save: (matrix: Matrix, quietHours: QuietHours) =>
    sendJson<{ ok: boolean; preferences?: Matrix; quietHours?: QuietHours }>("/api/notifications/preferences", "PATCH", {
      ...matrix,
      quiet_hours: quietHours,
    }),
}

/** Only the rows on the page, every channel a real boolean. */
export function pickMatrix(source: Matrix | undefined): Matrix {
  const out: Matrix = {}
  for (const event of NOTIFICATION_EVENTS) {
    const row = source?.[event.id]
    out[event.id] = {
      email_enabled: Boolean(row?.email_enabled),
      slack_enabled: Boolean(row?.slack_enabled),
      bell_enabled: Boolean(row?.bell_enabled),
    }
  }
  return out
}

export function sameMatrix(a: Matrix, b: Matrix): boolean {
  return NOTIFICATION_EVENTS.every((event) => CHANNELS.every(({ key }) => a[event.id]?.[key] === b[event.id]?.[key]))
}

export function sameQuiet(a: QuietHours, b: QuietHours): boolean {
  return a.enabled === b.enabled && a.from === b.from && a.to === b.to && a.timezone === b.timezone
}

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
  } catch {
    return "UTC"
  }
}

/** "Pacific Daylight Time" for America/Los_Angeles; the IANA name when the browser cannot name it. */
export function timeZoneLabel(zone: string, at: Date = new Date()): string {
  try {
    const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "long" })
      .formatToParts(at)
      .find((p) => p.type === "timeZoneName")
    return part?.value || zone
  } catch {
    return zone
  }
}

const CONNECTED = new Set(["active", "connected", "syncing", "healthy"])

/** Is a Slack connector connected for this workspace? Matches the backend's usable statuses. */
export function slackConnected(connectors: Array<{ vendor?: string; type?: string; status?: string }> | undefined): boolean {
  return (connectors ?? []).some((c) => {
    const vendor = String(c.vendor || c.type || "").toLowerCase()
    return vendor === "slack" && CONNECTED.has(String(c.status || "").toLowerCase())
  })
}
