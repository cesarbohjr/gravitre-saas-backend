import type { Conversation } from "@/types/api"

export type HistoryDateFilter = "all" | "today" | "week" | "archived"
export type HistorySort = "newest" | "oldest"

export const HISTORY_DATE_FILTER_OPTIONS: { value: HistoryDateFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "archived", label: "Archived" },
]

export const HISTORY_SORT_OPTIONS: { value: HistorySort; label: string }[] = [
  { value: "newest", label: "Most recent" },
  { value: "oldest", label: "Oldest" },
]

export const HISTORY_FILTER_STORAGE_KEY = "gravitre.chat.history.filter"
export const HISTORY_SORT_STORAGE_KEY = "gravitre.chat.history.sort"

export function isConversationArchived(conversation: Conversation): boolean {
  return Boolean(conversation.archived_at)
}

export function matchesHistoryDateFilter(
  conversation: Conversation,
  filter: HistoryDateFilter,
  now: Date = new Date(),
): boolean {
  const archived = isConversationArchived(conversation)
  if (filter === "archived") return archived
  if (archived) return false

  const updated = new Date(conversation.updated_at)
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfWeek = new Date(startOfToday.getTime() - 7 * 24 * 60 * 60 * 1000)

  if (filter === "today") return updated >= startOfToday
  if (filter === "week") return updated >= startOfWeek
  return true
}

export function sortConversations(items: Conversation[], sort: HistorySort): Conversation[] {
  return [...items].sort((a, b) => {
    const pin = Number(Boolean(b.pinned_at)) - Number(Boolean(a.pinned_at))
    if (pin !== 0) return pin
    const ta = new Date(a.updated_at).getTime()
    const tb = new Date(b.updated_at).getTime()
    return sort === "oldest" ? ta - tb : tb - ta
  })
}

export function parseHistoryDateFilter(value: unknown): HistoryDateFilter {
  if (value === "today" || value === "week" || value === "archived" || value === "all") return value
  return "all"
}

export function parseHistorySort(value: unknown): HistorySort {
  return value === "oldest" ? "oldest" : "newest"
}

export function readStoredHistoryDateFilter(): HistoryDateFilter {
  if (typeof window === "undefined") return "all"
  try {
    return parseHistoryDateFilter(window.localStorage.getItem(HISTORY_FILTER_STORAGE_KEY))
  } catch {
    return "all"
  }
}

export function readStoredHistorySort(): HistorySort {
  if (typeof window === "undefined") return "newest"
  try {
    return parseHistorySort(window.localStorage.getItem(HISTORY_SORT_STORAGE_KEY))
  } catch {
    return "newest"
  }
}

export function writeStoredHistoryDateFilter(filter: HistoryDateFilter): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(HISTORY_FILTER_STORAGE_KEY, filter)
  } catch {
    // private mode
  }
}

export function writeStoredHistorySort(sort: HistorySort): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(HISTORY_SORT_STORAGE_KEY, sort)
  } catch {
    // private mode
  }
}

export function emptyHistoryMessage(filter: HistoryDateFilter, searchQuery: string): string {
  if (searchQuery.trim()) return `No matches for "${searchQuery.trim()}"`
  if (filter === "archived") return "No archived conversations"
  if (filter === "today") return "No conversations from today"
  if (filter === "week") return "No conversations this week"
  return "No conversations yet"
}

export function optimisticRemoveConversations(
  current: { conversations: Conversation[] } | undefined,
  ids: string[],
): { conversations: Conversation[] } | undefined {
  if (!current) return current
  const remove = new Set(ids)
  return { conversations: current.conversations.filter((row) => !remove.has(row.id)) }
}
