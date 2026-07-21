import type { Conversation } from "@/types/api"

export type ConversationHistoryGroup = {
  label: string
  conversations: Conversation[]
}

/**
 * Group conversations into ChatGPT-style recency buckets.
 * Preserves input order within each bucket (caller must pass updated_at DESC).
 * Pinned threads are listed first under "Pinned" and omitted from date buckets.
 */
export function groupConversationsByRecency(
  conversations: Conversation[],
  nowMs: number = Date.now(),
): ConversationHistoryGroup[] {
  const now = new Date(nowMs)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
  const lastMonth = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)

  const pinned: Conversation[] = []
  const buckets = new Map<string, Conversation[]>()
  const monthOrder: string[] = []

  const pushBucket = (label: string, conv: Conversation) => {
    const list = buckets.get(label)
    if (list) {
      list.push(conv)
      return
    }
    buckets.set(label, [conv])
    monthOrder.push(label)
  }

  for (const conv of conversations) {
    if (conv.pinned_at) {
      pinned.push(conv)
      continue
    }
    const date = new Date(conv.updated_at)
    if (Number.isNaN(date.getTime())) {
      pushBucket("Older", conv)
      continue
    }
    if (date >= today) pushBucket("Today", conv)
    else if (date >= yesterday) pushBucket("Yesterday", conv)
    else if (date >= lastWeek) pushBucket("Previous 7 Days", conv)
    else if (date >= lastMonth) pushBucket("Previous 30 Days", conv)
    else {
      const label = date.toLocaleDateString(undefined, {
        month: "long",
        year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
      })
      pushBucket(label || "Older", conv)
    }
  }

  const fixedLabels = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days"]
  const groups: ConversationHistoryGroup[] = []
  if (pinned.length > 0) {
    groups.push({ label: "Pinned", conversations: pinned })
  }
  for (const label of fixedLabels) {
    const rows = buckets.get(label)
    if (rows?.length) groups.push({ label, conversations: rows })
  }
  for (const label of monthOrder) {
    if (fixedLabels.includes(label) || label === "Older") continue
    const rows = buckets.get(label)
    if (rows?.length) groups.push({ label, conversations: rows })
  }
  const older = buckets.get("Older")
  if (older?.length) groups.push({ label: "Older", conversations: older })
  return groups
}
