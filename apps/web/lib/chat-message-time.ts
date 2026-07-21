/** Message timestamp helpers — relative display, exact on hover; uses stored backend time. */

export type ChatMessageTimeMeta = {
  created_at?: string | null
}

const CLUSTER_MS = 2 * 60 * 1000

export function messageCreatedAt(message: {
  metadata?: unknown
}): string | null {
  const meta = message.metadata as ChatMessageTimeMeta | undefined
  const raw = meta?.created_at
  if (typeof raw !== "string" || !raw.trim()) return null
  const ms = Date.parse(raw)
  if (Number.isNaN(ms)) return null
  return raw
}

/** Relative label for recent messages; falls back to locale date/time for older. */
export function formatMessageRelativeTime(iso: string, nowMs: number = Date.now()): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return ""
  const diff = Math.max(0, nowMs - ms)
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`

  const date = new Date(ms)
  const now = new Date(nowMs)
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startMsg = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const dayDiff = Math.round((startToday.getTime() - startMsg.getTime()) / 86_400_000)
  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
  if (dayDiff === 1) return `Yesterday at ${time}`
  if (dayDiff < 7) {
    const weekday = date.toLocaleDateString(undefined, { weekday: "short" })
    return `${weekday} at ${time}`
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    hour: "numeric",
    minute: "2-digit",
  })
}

/** Full exact timestamp for title/tooltip (audit-aligned). */
export function formatMessageExactTime(iso: string): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return ""
  return new Date(ms).toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  })
}

/**
 * Whether to show a relative timestamp label for this message.
 * Consecutive same-role messages within CLUSTER_MS share one visible stamp
 * (exact time remains available via title on every bubble).
 */
export function shouldShowClusterTimestamp(
  messages: Array<{ id: string; role: string; metadata?: unknown }>,
  index: number,
): boolean {
  const current = messages[index]
  const iso = messageCreatedAt(current)
  if (!iso) return false
  if (index === 0) return true
  const prev = messages[index - 1]
  if (!prev || prev.role !== current.role) return true
  const prevIso = messageCreatedAt(prev)
  if (!prevIso) return true
  const delta = Math.abs(Date.parse(iso) - Date.parse(prevIso))
  return Number.isNaN(delta) || delta > CLUSTER_MS
}
